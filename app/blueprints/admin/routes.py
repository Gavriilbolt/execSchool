from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from ...models import Submission, Task, Block, User, db

bp = Blueprint("admin", __name__)

def is_admin():
    return current_user.is_authenticated and current_user.role == "admin"

@bp.route("/")
@login_required
def dashboard():
    if not is_admin():
        return "Forbidden", 403
    return render_template("admin/dashboard.html")

@bp.get("/api/admin/results.json")
@login_required
def results_json():
    if not is_admin():
        return jsonify({"error":"forbidden"}), 403

    block_id = request.args.get("block_id", type=int)
    q = db.session.query(
        Submission.id, Submission.created_at, Submission.verdict, Submission.points,
        User.display_name.label("user"),
        Task.title.label("task"), Task.block_id
    ).join(User, User.id==Submission.user_id)\
     .join(Task, Task.id==Submission.task_id)
    if block_id:
        q = q.filter(Task.block_id == block_id)

    rows = [{
        "id": s.id, "when": s.created_at.isoformat(), "verdict": s.verdict,
        "points": s.points, "user": s.user, "task": s.task, "block_id": s.block_id
    } for s in q.order_by(Submission.created_at.desc()).limit(200)]
    return jsonify(rows)
