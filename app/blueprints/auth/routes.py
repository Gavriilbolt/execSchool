# app/blueprints/auth/routes.py

from flask import render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user
from ...models import Student
from ...extensions import db, login_manager
from ...security import normalize_code, is_valid_code
from . import bp  # используем уже созданный в __init__.py Blueprint (url_prefix="/auth")


@login_manager.user_loader
def load_user(uid: str):
    try:
        # предпочтительно через session.get (SA2.0), но query.get тоже допустим
        return db.session.get(Student, int(uid))
    except Exception:
        return None


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        code = normalize_code(request.form.get("code", ""))

        if not is_valid_code(code):
            flash("Код должен состоять из 6 ЗАГЛАВНЫХ кириллических букв", "error")
            return render_template("auth/login.html"), 400

        student = Student.query.filter_by(auth_code=code).first()

        # опционально: автосоздание пользователя по коду
        if not student:
            student = Student(full_name=code)   # временно имя = код; админ поменяет
            student.set_auth_code(code)
            db.session.add(student)
            db.session.commit()

        login_user(student, remember=True)

        next_url = request.args.get("next") or url_for("main.index")
        return redirect(next_url)

    # GET
    return render_template("auth/login.html")


@bp.get("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
