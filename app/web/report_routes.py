# app/web/report_routes.py
import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import login_required
from app.core.decorators import role_required
from app.services import report_service
from app.services.discount_service import get_current_usd_rate
from app.web.forms import UploadPlanForm
from app.models.discount_models import PropertyType
from datetime import date
from flask import send_file
report_bp = Blueprint('report', __name__, template_folder='templates')

@report_bp.route('/download-plan-template')
@login_required
@role_required('ADMIN')
def download_plan_template():
    """Отдает пользователю сгенерированный Excel-шаблон для планов."""
    excel_stream = report_service.generate_plan_template_excel()
    return send_file(
        excel_stream,
        download_name='sales_plan_template.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@report_bp.route('/plan-fact', methods=['GET'])
@login_required
@role_required('ADMIN', 'MANAGER')
def plan_fact_report():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    prop_type = request.args.get('property_type', PropertyType.FLAT.value)

    # Получаем данные для основного отчета (как и раньше)
    usd_rate = get_current_usd_rate() or 12650
    # ИЗМЕНЕНИЕ: Получаем данные для итоговой сводки
    summary_data = report_service.get_monthly_summary_by_property_type(year, month)
    report_data, totals = report_service.generate_plan_fact_report(year, month, prop_type)
    return render_template('plan_fact_report.html',
                           title="План-фактный отчет",
                           data=report_data,
                           summary_data=summary_data,
                           totals=totals, # <-- Передаем новые данные в шаблон
                           years=[today.year - 1, today.year, today.year + 1],
                           months=range(1, 13),
                           property_types=list(PropertyType),
                           selected_year=year,
                           selected_month=month,
                           usd_to_uzs_rate=usd_rate,
                           selected_prop_type=prop_type)


@report_bp.route('/upload-plan', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def upload_plan():
    form = UploadPlanForm()
    if form.validate_on_submit():
        f = form.excel_file.data
        filename = secure_filename(f.filename)
        upload_folder = os.path.join(current_app.root_path, 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        f.save(file_path)

        try:
            year = form.year.data
            month = form.month.data
            result = report_service.process_plan_from_excel(file_path, year, month)
            flash(f"Файл успешно загружен. План на {month:02d}.{year} обновлен. {result}", "success")
        except Exception as e:
            flash(f"Произошла ошибка при обработке файла: {e}", "danger")

        return redirect(url_for('report.upload_plan'))

    return render_template('upload_plan.html', title="Загрузка плана", form=form)