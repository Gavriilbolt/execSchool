# app/blueprints/main/routes.py

from flask import render_template, request, jsonify
from flask_login import login_required, current_user
from ...models import Task, Submission
from ...extensions import db
from ...execengine_client import get_client
from ...services.scoring import score_batch
import requests
from . import bp


@bp.get("/")
@login_required
def index():
    task = Task.query.order_by(Task.id.asc()).first()
    return render_template("main/task.html", task=task)


@bp.post("/submit")
@login_required
def submit():
    task_id = request.form.get("task_id", type=int)
    code = request.form.get("code", "")

    if not task_id or not code:
        return jsonify({"error": "missing task_id or code"}), 400

    task = Task.query.get_or_404(task_id)

    # --- language_id с фолбэком ---
    language_id = getattr(task, "language_id", None)

    if language_id is None:
        alias = getattr(task, "language", None)
        if alias:
            _MAP = {
                "python3": 71,
                "python": 71,
                "py": 71,
                "cpp": 54,
                "c++": 54,
                "c": 50,
                "java": 62,
                "js": 63,
                "node": 63,
            }
            language_id = _MAP.get(str(alias).lower())

    if language_id is None:
        from flask import current_app
        language_id = current_app.config.get("EE_DEFAULT_LANGUAGE_ID")

    if not language_id:
        return jsonify({"error": "language_id not set for task"}), 400

    # --- тесты (минимум один пустой тест) ---
    tests = getattr(task, "tests", None) or [{"stdin": None, "expected_output": None}]

    # --- ExecEngine ---
    client = get_client()
    try:
        batch_resp = client.submit_batch(
            language_id=int(language_id),
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

    # --- оценивание ---
    points, verdict, raw = score_batch(task, batch_result)

    # --- запись отправки (минимально совместимо с админкой) ---
    sub = Submission(
        student_id=getattr(current_user, "id"),  # в моделях используется student_id
        task_id=task.id,
        status=verdict,        # админка читает Submission.status
        score=points,          # админка читает Submission.score
    )
    # Дополнительно сохраним то, что есть в модели (без предположений)
    if hasattr(Submission, "language_id"):
        sub.language_id = int(language_id)
    if hasattr(Submission, "code"):
        sub.code = code
    if hasattr(Submission, "source_code"):
        sub.source_code = code
    if hasattr(Submission, "raw_json"):
        sub.raw_json = raw
    if hasattr(Submission, "result_json"):
        sub.result_json = raw

    db.session.add(sub)
    db.session.commit()

    return jsonify({
        "verdict": verdict,
        "points": points,
        "batch_token": batch_token,
        "details": {"tests": len(tests)},
    })
