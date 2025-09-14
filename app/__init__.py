# app/__init__.py
from __future__ import annotations

import os
from typing import Type

from flask import Flask, request, jsonify, redirect, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

# единая точка инициализации расширений
# см. app/extensions.py: db = SQLAlchemy(), migrate = Migrate(), login_manager = LoginManager()
from .extensions import db, migrate, login_manager
from .config import Config


# -----------------------------
# Helpers
# -----------------------------

def _apply_env_overrides(app: Flask) -> None:
    """Поверх Config накладываем ENV-переменные, если они заданы.
    Это удобно для Docker/Kubernetes.
    """
    env = os.getenv

    # секреты/безопасность
    if env("SECRET_KEY"):
        app.config["SECRET_KEY"] = env("SECRET_KEY")

    # БД (поддержим оба варианта — SQLALCHEMY_DATABASE_URI и DATABASE_URL)
    db_uri = env("SQLALCHEMY_DATABASE_URI") or env("DATABASE_URL")
    if db_uri:
        app.config["SQLALCHEMY_DATABASE_URI"] = db_uri

    # Админ-токен
    admin_token = env("ADMIN_TOKEN")
    if admin_token:
        app.config["ADMIN_TOKEN"] = admin_token
    else:
        app.config.setdefault("ADMIN_TOKEN", "dev-admin-token")

    # Настройки ExecEngine (опционально)
    for cfg_key, env_key in (
        ("EE_BASE_URL", "EE_BASE_URL"),
        ("EE_USERNAME", "EE_USERNAME"),
        ("EE_PASSWORD", "EE_PASSWORD"),
        ("EE_DEFAULT_LANGUAGE_ID", "EE_DEFAULT_LANGUAGE_ID"),
    ):
        if env(env_key):
            if cfg_key == "EE_DEFAULT_LANGUAGE_ID":
                try:
                    app.config[cfg_key] = int(env(env_key))
                except ValueError:
                    app.config[cfg_key] = env(env_key)
            else:
                app.config[cfg_key] = env(env_key)

    # URL-схема
    if env("PREFERRED_URL_SCHEME"):
        app.config["PREFERRED_URL_SCHEME"] = env("PREFERRED_URL_SCHEME")

    # Работа за прокси/ingress
    if env("PROXY_FIX", "0").lower() not in ("0", "false", ""):
        x_for = int(env("PROXY_FIX_X_FOR", 1))
        x_proto = int(env("PROXY_FIX_X_PROTO", 1))
        x_host = int(env("PROXY_FIX_X_HOST", 1))
        x_port = int(env("PROXY_FIX_X_PORT", 1))
        x_prefix = int(env("PROXY_FIX_X_PREFIX", 0))
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=x_for, x_proto=x_proto,
                                x_host=x_host, x_port=x_port, x_prefix=x_prefix)  # type: ignore

    # Продовые флаги для cookie
    is_prod = (os.getenv("FLASK_ENV") == "production") or (os.getenv("ENV") == "production") or (app.config.get("ENV") == "production")
    if is_prod:
        app.config.setdefault("SESSION_COOKIE_SECURE", True)
        app.config.setdefault("REMEMBER_COOKIE_SECURE", True)
        app.config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")


def _register_error_handlers(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(e):  # type: ignore
        wants_json = request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
        if wants_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "not_found", "path": request.path}), 404
        return e

    @app.errorhandler(500)
    def internal_error(e):  # type: ignore
        wants_json = request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
        if wants_json or request.headers.get("X-Requested-With") == "XMLHttpRequest":
            return jsonify({"error": "internal_error"}), 500
        return e


def _register_util_routes(app: Flask) -> None:
    @app.get("/healthz")
    def healthz():
        return jsonify({"status": "ok"})

    @app.get("/readyz")
    def readyz():
        try:
            with db.engine.connect() as conn:
                conn.execute(db.text("SELECT 1"))
            db_ok = True
        except Exception:
            db_ok = False
        return jsonify({"status": "ok" if db_ok else "degraded", "db": db_ok}), (200 if db_ok else 503)

    @app.get("/version")
    def version():
        return jsonify({
            "version": app.config.get("APP_VERSION", "dev"),
            "env": app.config.get("ENV"),
        })


# -----------------------------
# App factory
# -----------------------------

def create_app(config_class: Type[Config] = Config) -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    # 1) базовая конфигурация
    app.config.from_object(config_class)

    # 2) ENV поверх конфига
    _apply_env_overrides(app)

    # 3) init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # настройка login_manager
    login_manager.login_view = "auth.login"
    login_manager.session_protection = "strong"  # type: ignore[attr-defined]

    # 4) блюпринты (импорт внутри фабрики)
    from .blueprints.auth import bp as auth_bp
    from .blueprints.main import bp as main_bp
    from .blueprints.admin import bp as admin_bp

    app.register_blueprint(auth_bp)                       # /auth/...
    app.register_blueprint(main_bp)                       # /
    app.register_blueprint(admin_bp, url_prefix="/admin") # /admin/...

    # 5) утилитарные маршруты и обработчики ошибок
    _register_util_routes(app)
    _register_error_handlers(app)

    # 6) чтобы Alembic «видел» модели
    with app.app_context():
        from . import models  # noqa: F401

    # 7) опциональная UI-админка на Flask-Admin
    if str(app.config.get("ENABLE_FLASK_ADMIN", os.getenv("ENABLE_FLASK_ADMIN", "0"))).lower() in ("1", "true", "yes"):
        try:
            from .admin import init_admin  # ожидается, что повесит UI на /panel
            init_admin(app)
        except Exception as e:
            app.logger.warning("Flask-Admin UI is enabled but failed to init: %s", e)

    return app


# -----------------------------
# Unauthorized handler
# -----------------------------

@login_manager.unauthorized_handler
def unauthorized():
    wants_json = request.accept_mimetypes.accept_json and not request.accept_mimetypes.accept_html
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    if wants_json or is_ajax:
        return jsonify({"error": "unauthorized"}), 401
    return redirect(url_for("auth.login", next=request.url))
