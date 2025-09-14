# app/models.py
from datetime import datetime
import re
from flask_login import UserMixin

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSONB

# Если ты используешь app/extensions.py с db = SQLAlchemy(), то лучше так:
try:
    # главный путь — db из extensions
    from .extensions import db  # type: ignore
except Exception:
    # запасной путь — чтобы CLI не падал, если импорт extensions пока не доступен
    db = SQLAlchemy()

# === Вспомогательная валидация кода (6 заглавных кириллических букв) ===
CYR_CODE_RE = re.compile(r"^[А-ЯЁ]{6}$")


def validate_cyr_code(code: str):
    if not CYR_CODE_RE.match(code or ""):
        raise ValueError("Код должен состоять из 6 заглавных кириллических букв (А-Я, Ё)")


# === Справочники дисциплин и модулей ===
class Discipline(db.Model):
    __tablename__ = "disciplines"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    modules = db.relationship(
        "Module",
        backref="discipline",
        cascade="all, delete-orphan",
        order_by="Module.order",
    )


class Module(db.Model):
    __tablename__ = "modules"
    id = db.Column(db.Integer, primary_key=True)
    discipline_id = db.Column(
        db.Integer, db.ForeignKey("disciplines.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(120), nullable=False)
    order = db.Column(db.Integer, default=1)
    tasks = db.relationship(
        "Task",
        backref="module",
        cascade="all, delete-orphan",
        order_by="Task.order",
    )


# === Учебные группы и студенты ===
class StudyGroup(db.Model):
    __tablename__ = "study_groups"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text, default="")
    students = db.relationship("Student", backref="group", cascade="all, delete-orphan")


class Student(UserMixin, db.Model):
    __tablename__ = "students"
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(200), nullable=False)
    auth_code = db.Column(db.String(6), unique=True, nullable=False, index=True)
    group_id = db.Column(db.Integer, db.ForeignKey("study_groups.id", ondelete="SET NULL"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_auth_code(self, code: str):
        code = (code or "").upper()
        validate_cyr_code(code)
        self.auth_code = code

    def __repr__(self):
        return f"<Student {self.id} {self.auth_code}>"


# === Задачи и тесты ===
class Task(db.Model):
    __tablename__ = "tasks"
    id = db.Column(db.Integer, primary_key=True)
    module_id = db.Column(
        db.Integer, db.ForeignKey("modules.id", ondelete="CASCADE"), nullable=False
    )
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)  # условие (markdown/HTML)
    input_format = db.Column(db.Text, default="")  # описание входа
    output_format = db.Column(db.Text, default="")  # описание выхода
    examples = db.Column(JSONB, default=list)  # список {input, output, note}
    order = db.Column(db.Integer, default=1)
    max_score = db.Column(db.Integer, default=100)

    tests = db.relationship(
        "TaskTest",
        backref="task",
        cascade="all, delete-orphan",
        order_by="TaskTest.order",
    )


class TaskTest(db.Model):
    __tablename__ = "task_tests"
    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(
        db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    order = db.Column(db.Integer, default=1)
    input_data = db.Column(db.Text, nullable=False)
    expected_output = db.Column(db.Text, nullable=False)
    points = db.Column(db.Integer, default=0)
    hidden = db.Column(db.Boolean, default=True)  # скрыто от студента


# === Отправки (интеграция с ExecEngine) ===
class Submission(db.Model):
    __tablename__ = "submissions"
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id = db.Column(
        db.Integer, db.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True
    )
    code = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(32), default="python")
    status = db.Column(db.String(32), default="queued")  # queued/running/ok/failed
    score = db.Column(db.Integer, default=0)
    runtime_ms = db.Column(db.Integer, default=0)
    result = db.Column(JSONB, default=dict)  # произвольный JSON от EE
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    student = db.relationship(
        "Student", backref=db.backref("submissions", cascade="all, delete-orphan")
    )
    task = db.relationship(
        "Task", backref=db.backref("submissions", cascade="all, delete-orphan")
    )

# Под сводки — будем делать SQL VIEW в миграциях (см. alembic script), из приложения читать обычным SELECT.
