#app/blueprints/admin/__init__.py
from flask import Blueprint

bp = Blueprint("admin", __name__)  # ВАЖНО: без url_prefix здесь!
from . import routes  # noqa
