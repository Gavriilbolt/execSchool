from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_user, logout_user
from ...models import User
from ...extensions import db, login_manager
from ...security import normalize_code, is_valid_code

bp = Blueprint("auth", __name__)

@login_manager.user_loader
def load_user(uid):
    return User.query.get(int(uid))

@bp.route("/auth", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        code = normalize_code(request.form.get("code"))
        if not is_valid_code(code):
            flash("Код должен состоять из 6 заглавных кириллических букв", "error")
            return render_template("auth/login.html")
        user = User.query.filter_by(code6=code).first()
        if not user:
            # По желанию: автосоздание студента по коду
            user = User(code6=code, display_name=code)
            db.session.add(user); db.session.commit()
        login_user(user, remember=True)
        return redirect(url_for("main.index"))
    return render_template("auth/login.html")

@bp.route("/logout")
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
