# app/__init__.py
from flask import Flask, request, jsonify, redirect, url_for
from .extensions import db, migrate, login_manager
from .config import Config

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Регистрируем блюпринты
    from .blueprints.auth import bp as auth_bp
    from .blueprints.main import bp as main_bp
    from .blueprints.admin import bp as admin_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # ВАЖНО: подхватить модели, чтобы alembic «видел» таблицы
    with app.app_context():
        from . import models  # noqa: F401

    return app


@login_manager.unauthorized_handler
def unauthorized():
    wants_json = request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if wants_json or is_ajax:
        return jsonify({"error": "unauthorized"}), 401
    return redirect(url_for("auth.login", next=request.url))