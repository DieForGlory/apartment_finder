from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user

from ..core.decorators import permission_required
from ..models.user_models import User
from ..core.extensions import db
from .forms import CreateUserForm, ChangePasswordForm, RoleForm
from ..models.user_models import User, Role, Permission

auth_bp = Blueprint('auth', __name__, template_folder='templates')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            next_page = request.args.get('next')
            return redirect(next_page or url_for('main.index'))
        else:
            flash('Неверный логин или пароль.', 'danger')

    return render_template('login.html', title='Вход в систему')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы.', 'success')
    return redirect(url_for('auth.login'))


@auth_bp.route('/users', methods=['GET', 'POST'])
@login_required
@permission_required('manage_users') # <-- Меняем на право
def user_management():
    form = CreateUserForm()
    # V-- ДОБАВЛЯЕМ ЗАГРУЗКУ РОЛЕЙ В ФОРМУ --V
    form.role.choices = [(r.id, r.name) for r in Role.query.order_by('name').all()]
    # A---------------------------------------A

    if form.validate_on_submit():
        role_obj = Role.query.get(form.role.data) # Получаем объект роли по ID
        user = User(username=form.username.data, role=role_obj, full_name=form.full_name.data,
            email=form.email.data,
            phone_number=form.phone_number.data) # Присваиваем объект
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Пользователь {user.username} успешно создан.', 'success')
        return redirect(url_for('auth.user_management'))

    users = User.query.order_by(User.id).all()
    return render_template('user_management.html', title="Управление пользователями", users=users, form=form)


@auth_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@permission_required('manage_users')
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Вы не можете удалить свою учетную запись.', 'danger')
        return redirect(url_for('auth.user_management'))

    user_to_delete = User.query.get_or_404(user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Пользователь {user_to_delete.username} удален.', 'success')
    return redirect(url_for('auth.user_management'))


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    form = ChangePasswordForm()
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Введен неверный текущий пароль.', 'danger')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            flash('Ваш пароль успешно изменен.', 'success')
            return redirect(url_for('main.selection'))

    return render_template('change_password.html', title="Смена пароля", form=form)


@auth_bp.route('/roles')
@login_required
@permission_required('manage_users')  # Доступ к управлению ролями даем тем, кто может управлять пользователями
def manage_roles():
    """Главная страница управления ролями."""
    roles = Role.query.order_by(Role.name).all()
    return render_template('manage_roles.html', title="Управление ролями", roles=roles)


# app/web/auth_routes.py

# app/web/auth_routes.py

# app/web/auth_routes.py

# app/web/auth_routes.py

@auth_bp.route('/role/edit/<int:role_id>', methods=['GET', 'POST'])
@auth_bp.route('/role/new', methods=['GET', 'POST'], defaults={'role_id': None})
@login_required
@permission_required('manage_users')
def role_form(role_id):
    if role_id:
        role = Role.query.get_or_404(role_id)
        form = RoleForm(obj=role)
        title = f"Редактирование роли: {role.name}"
    else:
        role = Role()
        form = RoleForm()
        title = "Создание новой роли"

    # Эта логика для валидации при сохранении
    form.permissions.choices = [(p.id, p.description) for p in Permission.query.order_by('description').all()]

    if form.validate_on_submit():
        role.name = form.name.data
        selected_permissions = Permission.query.filter(Permission.id.in_(form.permissions.data)).all()
        role.permissions = selected_permissions

        if not role_id:
            db.session.add(role)

        db.session.commit()
        flash(f"Роль '{role.name}' успешно сохранена.", "success")
        return redirect(url_for('auth.manage_roles'))

    # --- ГОТОВИМ ДАННЫЕ ДЛЯ РУЧНОЙ ОТРИСОВКИ В ШАБЛОНЕ ---
    all_permissions = Permission.query.order_by('description').all()
    selected_permission_ids = {p.id for p in role.permissions}

    return render_template(
        'role_form.html',
        title=title,
        form=form,
        all_permissions=all_permissions,  # Передаем все возможные права
        selected_permission_ids=selected_permission_ids  # Передаем ID уже выбранных прав
    )


@auth_bp.route('/role/delete/<int:role_id>', methods=['POST'])
@login_required
@permission_required('manage_users')
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    # Защита от удаления роли, которая кому-то присвоена
    if role.users.count() > 0:
        flash(f"Нельзя удалить роль '{role.name}', так как она присвоена пользователям.", 'danger')
        return redirect(url_for('auth.manage_roles'))

    db.session.delete(role)
    db.session.commit()
    flash(f"Роль '{role.name}' успешно удалена.", 'success')
    return redirect(url_for('auth.manage_roles'))

# --- КОНЕЦ: РОУТЫ ДЛЯ УПРАВЛЕНИЯ РОЛЯМИ ---