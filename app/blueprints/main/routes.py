from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from ...models import Task, Submission, db
from ...execengine_client import get_client
from ...services.scoring import score_batch
import requests


bp = Blueprint("main", __name__)

@bp.route("/")
@login_required
def index():
    task = Task.query.order_by(Task.id.asc()).first()
    return render_template("main/task.html", task=task)

@bp.post("/submit")
@login_required
def submit():
    task_id = int(request.form["task_id"])
    code = request.form["code"]
    task = Task.query.get_or_404(task_id)

    tests = getattr(task, "tests", None) or [{"stdin": None, "expected_output": None}]
    language_id = getattr(task, "language_id", None)
    if language_id is None:
        return jsonify({"error": "language_id not set for task"}), 400

    client = get_client()
    try:
        batch_resp = client.submit_batch(
            language_id=language_id,
            source_code=code,
            tests=tests,
        )
        batch_token = batch_resp.get("batch_token")
        batch_result = client.wait_batch_results(batch_token) if batch_token else batch_resp
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", 502)
        text = getattr(e.response, "text", "")[:300]
        return jsonify({"error": f"ExecEngine HTTP {status}", "details": text}), 502
    except Exception as e:
        return jsonify({"error": f"ExecEngine error: {e}"}), 500

    points, verdict, raw = score_batch(task, batch_result)

    sub = Submission(
        user_id=current_user.id, task_id=task.id,
        code=code, lang=str(language_id),
        verdict=verdict, time_ms=None, memory_kb=None,
        points=points, raw_json=raw
    )
    db.session.add(sub); db.session.commit()

    return jsonify({
        "verdict": verdict,
        "points": points,
        "batch_token": batch_token,
        "details": {"tests": len(tests)}
    })
