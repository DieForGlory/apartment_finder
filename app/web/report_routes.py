# app/web/report_routes.py
import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required
from app.core.decorators import role_required
from app.services import report_service
from app.services.discount_service import get_current_usd_rate
from app.web.forms import UploadPlanForm
from app.models.discount_models import PropertyType
from datetime import date
from flask import send_file
import json

report_bp = Blueprint('report', __name__, template_folder='templates')


@report_bp.route('/download-plan-template')
@login_required
@role_required('ADMIN')
def download_plan_template():
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

    usd_rate = get_current_usd_rate() or 12650
    summary_data = report_service.get_monthly_summary_by_property_type(year, month)
    report_data, totals = report_service.generate_plan_fact_report(year, month, prop_type)
    return render_template('plan_fact_report.html',
                           title="План-фактный отчет",
                           data=report_data,
                           summary_data=summary_data,
                           totals=totals,
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


@report_bp.route('/project-dashboard/<path:complex_name>')
@login_required
@role_required('ADMIN', 'MANAGER')
def project_dashboard(complex_name):
    # 1. Получаем тип недвижимости из URL
    selected_prop_type = request.args.get('property_type', None)

    # 2. Вызываем сервис ОДИН РАЗ с учётом фильтра
    data = report_service.get_project_dashboard_data(complex_name, selected_prop_type)

    if not data:
        abort(404)

    # 3. Готовим данные для шаблона, используя одну и ту же переменную 'data'
    property_types = [pt.value for pt in PropertyType]
    charts_json = json.dumps(data.get('charts', {}))
    usd_rate = get_current_usd_rate() or current_app.config.get('USD_TO_UZS_RATE', 12650.0)

    # 4. Передаем в шаблон правильные данные
    return render_template(
        'project_dashboard.html',
        title=f"Аналитика по проекту {complex_name}",
        data=data,
        charts_json=charts_json,
        property_types=property_types,
        selected_prop_type=selected_prop_type,
        usd_to_uzs_rate=usd_rate
    )
@report_bp.route('/export-plan-fact')
@login_required
@role_required('ADMIN', 'MANAGER')
def export_plan_fact():
    """
    Обрабатывает запрос на экспорт план-фактного отчета в Excel.
    """
    today = date.today()
    # Получаем те же параметры, что и для отображения отчета
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    prop_type = request.args.get('property_type', PropertyType.FLAT.value)

    # Вызываем сервис для генерации файла
    excel_stream = report_service.generate_plan_fact_excel(year, month, prop_type)

    if excel_stream is None:
        flash("Нет данных для экспорта.", "warning")
        return redirect(url_for('report.plan_fact_report'))

    # Формируем имя файла и отправляем его пользователю
    filename = f"plan_fact_report_{prop_type}_{month:02d}_{year}.xlsx"
    return send_file(
        excel_stream,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
