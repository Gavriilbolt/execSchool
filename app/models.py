from datetime import datetime
from .extensions import db
from flask_login import UserMixin

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code6 = db.Column(db.String(6), unique=True, index=True, nullable=False)   # АААААА
    display_name = db.Column(db.String(120))
    role = db.Column(db.String(16), default="student")  # "student" | "admin"

    def get_id(self):
        return str(self.id)

class Block(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    order = db.Column(db.Integer, default=0)

class Task(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    block_id = db.Column(db.Integer, db.ForeignKey("block.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    language = db.Column(db.String(32), nullable=False)   # e.g. "python3"
    starter_code = db.Column(db.Text, default="")
    max_points = db.Column(db.Integer, default=100)
    block = db.relationship("Block")
    language_id = db.Column(db.Integer, nullable=False, default=71)  # пример: python3, поменяй под свои id
    tests = db.Column(db.JSON, nullable=True)  # [{"stdin": "...", "expected_output": "..."}]


class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    code = db.Column(db.Text, nullable=False)
    lang = db.Column(db.String(32), nullable=False)
    verdict = db.Column(db.String(32), nullable=False)  # "OK" / "WA" / "RE" / "TLE" ...
    time_ms = db.Column(db.Integer)
    memory_kb = db.Column(db.Integer)
    points = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    raw_json = db.Column(db.JSON)  # полный ответ ExecEngine
