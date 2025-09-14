# app/blueprints/admin/routes.py

from flask import render_template, jsonify, request, current_app, abort
from flask_login import login_required, current_user
from jinja2 import TemplateNotFound

from ...extensions import db
from ...models import Submission, Task, Student  # Module убрал — не используется

from . import bp


def has_admin_access() -> bool:
    """
    Доступ в админку: пользователь ДОЛЖЕН быть залогинен,
    и ЛИБО иметь флаг is_admin, ЛИБО предъявить валидный ADMIN_TOKEN.
    """
    if not getattr(current_user, "is_authenticated", False):
        return False

    if getattr(current_user, "is_admin", False):
        return True

    cfg_token = current_app.config.get("ADMIN_TOKEN")
    tok = request.headers.get("X-Admin-Token") or request.args.get("admin_token")
    return bool(cfg_token) and tok == cfg_token


@bp.get("")
@bp.get("/")
@login_required
def dashboard():
    if not has_admin_access():
        abort(403)

    try:
        return render_template("admin/dashboard.html")
    except TemplateNotFound:
        # временная заглушка, пока нет шаблона
        return "ADMIN OK", 200


@bp.get("/api/results.json")  # <-- убрали лишнее 'admin' в пути
@login_required
def results_json():
    if not has_admin_access():
        return jsonify({"error": "forbidden"}), 403

    module_id = request.args.get("module_id", type=int)

    q = (
        db.session.query(
            Submission.id,
            Submission.created_at,
            Submission.status,
            Submission.score,
            Student.full_name.label("student"),
            Task.title.label("task"),
            Task.module_id.label("module_id"),
        )
        .join(Student, Student.id == Submission.student_id)
        .join(Task, Task.id == Submission.task_id)
    )
    if module_id:
        q = q.filter(Task.module_id == module_id)

    rows = [
        {
            "id": r.id,
            "when": r.created_at.isoformat() if r.created_at else None,
            "status": r.status,
            "score": r.score,
            "student": r.student,
            "task": r.task,
            "module_id": r.module_id,
        }
        for r in q.order_by(Submission.created_at.desc()).limit(200).all()
    ]
    return jsonify(rows)
