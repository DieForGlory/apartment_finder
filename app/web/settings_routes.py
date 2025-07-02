from flask import Blueprint, render_template, request, flash, redirect, url_for
from flask_login import login_required
from app.core.decorators import role_required
from app.services import settings_service
from .forms import CalculatorSettingsForm

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