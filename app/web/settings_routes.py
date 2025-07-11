# app/web/settings_routes.py

from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app.core.decorators import permission_required # <-- Используем новый декоратор
from app.services import settings_service
from .forms import CalculatorSettingsForm
from ..core.extensions import db
from ..models.estate_models import EstateHouse
from ..models.user_models import User, EmailRecipient

settings_bp = Blueprint('settings', __name__, template_folder='templates')

@settings_bp.route('/calculator-settings', methods=['GET', 'POST'])
@login_required
@permission_required('manage_settings') # <-- ИЗМЕНЕНИЕ
def manage_settings():
    form = CalculatorSettingsForm()
    settings = settings_service.get_calculator_settings()

    if form.validate_on_submit():
        settings_service.update_calculator_settings(request.form)
        flash('Настройки калькуляторов успешно обновлены.', 'success')
        return redirect(url_for('settings.manage_settings'))

    # Заполняем форму текущими значениями из БД
    form.standard_installment_whitelist.data = settings.standard_installment_whitelist
    form.dp_installment_whitelist.data = settings.dp_installment_whitelist
    form.dp_installment_max_term.data = settings.dp_installment_max_term
    form.time_value_rate_annual.data = settings.time_value_rate_annual
    # Добавлено для корректного отображения
    if hasattr(settings, 'standard_installment_min_dp_percent'):
        form.standard_installment_min_dp_percent.data = settings.standard_installment_min_dp_percent


    return render_template('calculator_settings.html', title="Настройки калькуляторов", form=form)

@settings_bp.route('/manage-inventory-exclusions', methods=['GET', 'POST'])
@login_required
@permission_required('manage_settings') # <-- ИЗМЕНЕНИЕ
def manage_inventory_exclusions():
    """Страница для управления исключенными ЖК из сводки по остаткам."""
    if request.method == 'POST':
        complex_name = request.form.get('complex_name')
        if complex_name:
            message, category = settings_service.toggle_complex_exclusion(complex_name)
            flash(message, category)
        return redirect(url_for('settings.manage_inventory_exclusions'))

    # Получаем список всех ЖК и исключенных ЖК
    all_complexes = db.session.query(EstateHouse.complex_name).distinct().order_by(EstateHouse.complex_name).all()
    excluded_complexes = settings_service.get_all_excluded_complexes()
    excluded_names = {c.complex_name for c in excluded_complexes}

    return render_template(
        'manage_exclusions.html',
        title="Исключения в сводке по остаткам",
        all_complexes=[c[0] for c in all_complexes],
        excluded_names=excluded_names
    )

@settings_bp.route('/email-recipients', methods=['GET', 'POST'])
@login_required
@permission_required('manage_settings')
def manage_email_recipients():
    """Страница для управления получателями email-уведомлений."""
    if request.method == 'POST':
        # Получаем ID пользователей, отмеченных галочками
        selected_user_ids = request.form.getlist('recipient_ids', type=int)

        # Полностью очищаем старый список подписчиков
        EmailRecipient.query.delete()

        # Создаем новый список на основе выбора
        for user_id in selected_user_ids:
            recipient = EmailRecipient(user_id=user_id)
            db.session.add(recipient)

        db.session.commit()
        flash('Список получателей уведомлений успешно обновлен.', 'success')
        return redirect(url_for('settings.manage_email_recipients'))

    # Для GET-запроса получаем всех пользователей и ID тех, кто уже подписан
    all_users = User.query.order_by(User.full_name).all()
    subscribed_user_ids = {r.user_id for r in EmailRecipient.query.all()}

    return render_template(
        'manage_recipients.html',
        title="Получатели уведомлений",
        all_users=all_users,
        subscribed_user_ids=subscribed_user_ids
    )