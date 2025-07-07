from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app.core.decorators import role_required
from app.services import settings_service
from .forms import CalculatorSettingsForm
from flask import render_template, request, flash, redirect, url_for
from ..core.extensions import db
from ..models.estate_models import EstateHouse
from ..services import settings_service

settings_bp = Blueprint('settings', __name__, template_folder='templates')

@settings_bp.route('/calculator-settings', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
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

    return render_template('calculator_settings.html', title="Настройки калькуляторов", form=form)

@settings_bp.route('/manage-inventory-exclusions', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN', 'MANAGER')
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