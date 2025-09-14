# app/admin.py
from flask import Blueprint, request, jsonify, render_template, current_app, redirect, url_for
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
from flask_admin.actions import action
from wtforms import ValidationError
from .models import db, Discipline, Module, StudyGroup, Student, Task, TaskTest, Submission, validate_cyr_code
import csv
import io


admin_bp = Blueprint('admin_extra', __name__, template_folder='templates')


# === Безопасность: простая защита по токену в заголовке/куках ===
# В проде подключи нормальную аутентификацию.
@admin_bp.before_app_request
def admin_guard():
    if request.path.startswith('/admin') and not request.path.startswith('/admin/login'):
        token = request.cookies.get('admin_token') or request.headers.get('X-Admin-Token')
        need = current_app.config.get('ADMIN_TOKEN')
        if need and token != need:
            return redirect(url_for('admin_extra.login'))


@admin_bp.route('/admin/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        token = request.form.get('token')
        if token and token == current_app.config.get('ADMIN_TOKEN'):
            resp = redirect('/admin')
            resp.set_cookie('admin_token', token, httponly=True)
            return resp
    return render_template('admin/login.html')


# === Flask‑Admin CRUD ===
class RequireAuth(ModelView):
    def is_accessible(self):
    # токен уже проверен в before_request
        return True


class StudentView(RequireAuth):
    column_list = ['full_name', 'auth_code', 'group']
    column_searchable_list = ['full_name', 'auth_code']
    column_filters = ['group']


    def on_model_change(self, form, model, is_created):
        try:
            validate_cyr_code(model.auth_code.upper())
            model.auth_code = model.auth_code.upper()
        except Exception as e:
            raise ValidationError(str(e))


class TaskTestInline(ModelView):
    can_create = True
    can_edit = True
    can_delete = True
    column_list = ['order', 'points', 'hidden']
    form_columns = ['order', 'input_data', 'expected_output', 'points', 'hidden']


class TaskView(RequireAuth):
    column_list = ['module', 'title', 'order', 'max_score']
    column_filters = ['module.discipline', 'module']
    column_searchable_list = ['title', 'description']
    inline_models = [(TaskTest, dict(form_columns=['order','input_data','expected_output','points','hidden']))]


class SubmissionView(RequireAuth):
    column_list = ['created_at', 'student', 'task', 'status', 'score', 'runtime_ms']
    column_filters = ['status', 'student', 'task']
    column_default_sort = ('created_at', True)


# Инициализация
admin = Admin(name='Учебная админка', template_mode='bootstrap4', endpoint='admin')


def init_admin(app):
    admin.init_app(app)
    app.register_blueprint(admin_bp)


    admin.add_view(RequireAuth(Discipline, db.session, category='Учебные'))
    admin.add_view(RequireAuth(Module, db.session, category='Учебные'))
    admin.add_view(RequireAuth(StudyGroup, db.session, category='Учебные'))
    admin.add_view(StudentView(Student, db.session, category='Учебные'))
    admin.add_view(TaskView(Task, db.session, category='Задачи'))
    admin.add_view(RequireAuth(TaskTest, db.session, category='Задачи'))
    admin.add_view(SubmissionView(Submission, db.session, category='Отправки'))


# === Кастом: CSV импорт/экспорт студентов для группы ===
@admin_bp.route('/admin/groups/<int:group_id>/roster')
def group_roster(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    return render_template('admin/roster.html', group=group)


@admin_bp.post('/admin/groups/<int:group_id>/roster/import')
def roster_import(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    f = request.files.get('file')
    if not f:
        return 'no file', 400
    data = io.StringIO(f.stream.read().decode('utf-8'))
    reader = csv.DictReader(data)
    created, updated, errors = 0, 0, []
    for i, row in enumerate(reader, start=1):
        name = (row.get('full_name') or '').strip()
        code = (row.get('auth_code') or '').strip().upper()
        try:
            validate_cyr_code(code)
        except Exception as e:
            errors.append(f'Строка {i}: {e}')
            continue
        st = Student.query.filter_by(auth_code=code).first()
        if st:
            st.full_name = name or st.full_name
            st.group = group
            updated += 1
        else:
            st = Student(full_name=name, group=group)
            st.set_auth_code(code)
            db.session.add(st)
            created += 1
    db.session.commit()
    return jsonify({'created': created, 'updated': updated, 'errors': errors})


@admin_bp.get('/admin/groups/<int:group_id>/roster/export')
def roster_export(group_id):
    group = StudyGroup.query.get_or_404(group_id)
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(['full_name','auth_code'])
    for s in group.students:
        w.writerow([s.full_name, s.auth_code])
    return current_app.response_class(out.getvalue(), mimetype='text/csv', headers={
        'Content-Disposition': f'attachment; filename="group_{group.id}_roster.csv"'
    })


# === Сводная по группе/модулям ===
@admin_bp.get('/admin/scoreboard')
def scoreboard():
    # Варианты фильтров: group_id, discipline_id
    group_id = request.args.get('group_id', type=int)
    discipline_id = request.args.get('discipline_id', type=int)


    sql = "SELECT * FROM v_group_module_scores WHERE 1=1"
    params = {}
    if group_id:
        sql += " AND group_id = :gid"; params['gid'] = group_id
    if discipline_id:
        sql += " AND discipline_id = :did"; params['did'] = discipline_id


    rows = db.session.execute(db.text(sql), params).mappings().all()


    # перестроим в удобную матрицу: student x module
    modules = []
    students = {}
    for r in rows:
        key = (r['module_id'], r['module_name'])
        if key not in modules:
            modules.append(key)
        stud = students.setdefault(r['student_id'], {
            'student_id': r['student_id'],
            'student_name': r['student_name'],
            'scores': {}
        })
        stud['scores'][r['module_id']] = r['score']


    modules_sorted = sorted(modules, key=lambda x: x[0])
    students_list = list(students.values())


    return render_template('admin/scoreboard.html',
                                    groups=StudyGroup.query.all(),
                                    disciplines=Discipline.query.all(),
                                    modules=modules_sorted,
                                    students=students_list,
                                    selected_group=group_id,
                                    selected_discipline=discipline_id)