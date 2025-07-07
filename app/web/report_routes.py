# app/web/report_routes.py
import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, abort
from flask_login import login_required
from app.core.decorators import role_required
from app.services import report_service, selection_service
from app.services.discount_service import get_current_usd_rate
from app.web.forms import UploadPlanForm
from app.models.discount_models import PropertyType
from datetime import date, datetime
from flask import send_file
import json
from app.services import report_service, currency_service
from app.models.finance_models import CurrencySettings
from app.services import report_service, currency_service, inventory_service
from app.models.finance_models import CurrencySettings
report_bp = Blueprint('report', __name__, template_folder='templates')


@report_bp.route('/inventory-summary')
@login_required
@role_required('ADMIN', 'MANAGER')
def inventory_summary():
    """
    Отображает сводку по товарному запасу.
    """
    summary_by_complex, overall_summary = inventory_service.get_inventory_summary_data()

    # ИЗМЕНЕНИЕ: Убираем сортировку здесь и передаем словари как есть

    usd_rate = currency_service.get_current_effective_rate()

    return render_template(
        'inventory_summary.html',
        title="Сводка по товарному запасу",
        summary=summary_by_complex,
        overall_summary=overall_summary,
        usd_to_uzs_rate=usd_rate
    )


@report_bp.route('/export-inventory-summary')
@login_required
@role_required('ADMIN', 'MANAGER')
def export_inventory_summary():
    """
    Формирует и отдает Excel-файл со сводкой по остаткам.
    """
    selected_currency = request.args.get('currency', 'UZS')
    usd_rate = currency_service.get_current_effective_rate()

    # 1. Здесь мы получаем данные в переменную `summary_by_complex`
    summary_by_complex, _ = inventory_service.get_inventory_summary_data()

    # 2. ИСПОЛЬЗУЕМ ЭТУ ЖЕ ПЕРЕМЕННУЮ `summary_by_complex` здесь
    excel_stream = inventory_service.generate_inventory_excel(summary_by_complex, selected_currency, usd_rate)

    if excel_stream is None:
        flash("Нет данных для экспорта.", "warning")
        return redirect(url_for('report.inventory_summary'))

    filename = f"inventory_summary_{selected_currency}.xlsx"
    return send_file(
        excel_stream,
        download_name=filename,
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

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

    usd_rate = currency_service.get_current_effective_rate()
    summary_data = report_service.get_monthly_summary_by_property_type(year, month)
    report_data, totals = report_service.generate_plan_fact_report(year, month, prop_type)

    # ВЫЗЫВАЕМ НОВУЮ ФУНКЦИЮ
    grand_totals = report_service.calculate_grand_totals(year, month)

    return render_template('plan_fact_report.html',
                           title="План-фактный отчет",
                           data=report_data,
                           summary_data=summary_data,
                           totals=totals,
                           grand_totals=grand_totals,  # И ПЕРЕДАЕМ РЕЗУЛЬТАТ В ШАБЛОН
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

@report_bp.route('/commercial-offer/complex/<int:sell_id>')
@login_required
def generate_complex_kp(sell_id):
    """
    Генерирует КП для сложных калькуляторов.
    Данные для расчета берутся из URL.
    """
    # 1. Получаем базовую информацию об объекте (для шапки)
    card_data = selection_service.get_apartment_card_data(sell_id)
    if not card_data.get('apartment'):
        abort(404)

    # 2. Получаем тип калькулятора и детали из параметров URL
    calc_type = request.args.get('calc_type')
    details_json = request.args.get('details')

    if not all([calc_type, details_json]):
        flash("Отсутствуют данные для генерации КП.", "danger")
        return redirect(url_for('main.apartment_details', sell_id=sell_id))

    try:
        details = json.loads(details_json)
    except json.JSONDecodeError:
        abort(400, "Некорректный формат данных (JSON).")
    if 'payment_schedule' in details:
        for payment in details['payment_schedule']:
            # Теперь строка приходит в формате 'YYYY-MM-DD',
            # поэтому убираем .split('T')[0]
            payment['payment_date'] = datetime.strptime(payment['payment_date'], '%Y-%m-%d').date()
    # 3. Получаем актуальную дату и курс валют
    current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    usd_rate = currency_service.get_current_effective_rate()

    # 4. Рендерим новый специальный шаблон
    return render_template(
        'commercial_offer_complex.html',
        title=f"КП (сложный расчет) по объекту ID {sell_id}",
        data=card_data,
        calc_type=calc_type,
        details=details,
        current_date=current_date,
        usd_to_uzs_rate=usd_rate
    )

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
    usd_rate = currency_service.get_current_effective_rate()

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

@report_bp.route('/currency-settings', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def currency_settings():
    if request.method == 'POST':
        # Обработка форм
        if 'set_source' in request.form:
            source = request.form.get('rate_source')
            currency_service.set_rate_source(source)
            flash(f"Источник курса изменен на '{source}'.", "success")

        if 'set_manual_rate' in request.form:
            try:
                rate = float(request.form.get('manual_rate'))
                currency_service.set_manual_rate(rate)
                flash(f"Ручной курс успешно установлен: {rate}.", "success")
            except (ValueError, TypeError):
                flash("Неверное значение для ручного курса.", "danger")

        return redirect(url_for('report.currency_settings'))

    settings = currency_service._get_settings() # Используем внутреннюю функцию для получения данных
    return render_template('currency_settings.html', settings=settings, title="Настройки курса валют")




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
