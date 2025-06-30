from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_user, logout_user, login_required, current_user
from ..models.user_models import User
from ..core.extensions import db
from .forms import CreateUserForm, ChangePasswordForm
from ..core.decorators import role_required

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
@role_required('ADMIN')
def user_management():
    form = CreateUserForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, role=form.role.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Пользователь {user.username} успешно создан.', 'success')
        return redirect(url_for('auth.user_management'))

    users = User.query.order_by(User.id).all()
    return render_template('user_management.html', title="Управление пользователями", users=users, form=form)


@auth_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
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