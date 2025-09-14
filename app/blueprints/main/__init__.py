#app/blueprints/main/__init__.py


from flask import Blueprint

bp = Blueprint("main", __name__)  # без url_prefix — мы вешаем его как корень "/"

from . import routes  # noqa
