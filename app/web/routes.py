import os
import json
from ..models.discount_models import PropertyType, PaymentMethod
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file, jsonify

from ..models.exclusion_models import ExcludedSell
from ..services.selection_service import find_apartments_by_budget, get_apartment_card_data
from ..core.extensions import db
from .forms import UploadExcelForm
from ..services.data_service import get_sells_with_house_info, get_filter_options
from ..services.email_service import send_email
from ..services.discount_service import (
    process_discounts_from_excel,
    generate_discount_template_excel,
    get_discounts_with_summary,
    create_new_version,
    create_blank_version,
    activate_version,
    update_discounts_for_version, get_current_usd_rate
)
from ..models.discount_models import Discount, DiscountVersion, ComplexComment

# Создаем Blueprint. 'web' - это имя, которое мы будем использовать для ссылки на эти роуты.
web_bp = Blueprint('web', __name__, template_folder='templates')



@web_bp.route('/download-template')
def download_template():
    """
    Генерирует и отдает пользователю для скачивания шаблон Excel.
    """
    excel_data_stream = generate_discount_template_excel()
    return send_file(
        excel_data_stream,
        download_name='discount_template.xlsx',
        as_attachment=True,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )


@web_bp.route('/')
def index():
    """
    Главная страница с таблицей и пагинацией.
    """
    page = request.args.get('page', 1, type=int)
    PER_PAGE = 40
    sells_pagination = get_sells_with_house_info(page=page, per_page=PER_PAGE)

    if not sells_pagination:
        flash("Не удалось загрузить данные о продажах.", "danger")
        return render_template('index.html', title='Ошибка', sells_pagination=None)

    return render_template('index.html', title='Главная', sells_pagination=sells_pagination)


@web_bp.route('/upload-discounts', methods=['GET', 'POST'])
def upload_discounts():
    """
    Страница для загрузки файла со скидками.
    Создает новую версию, наполняет ее из файла и делает активной.
    """
    form = UploadExcelForm()
    if form.validate_on_submit():
        f = form.excel_file.data
        filename = secure_filename(f.filename)

        upload_folder = os.path.join(current_app.root_path, 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)
        f.save(file_path)

        try:
            comment = f"Загрузка из файла: {filename}"
            new_version = create_blank_version(comment=comment)

            # process_discounts_from_excel добавит объекты Discount в текущую сессию
            result_message = process_discounts_from_excel(file_path, new_version.id)

            # Активируем версию ПОСЛЕ того, как данные для неё добавлены в сессию, но ДО финального коммита
            email_data = activate_version(
                new_version.id)  # activate_version тоже делает db.session.commit() внутри себя.

            # Если activate_version делает commit, то отдельный commit здесь может быть не нужен,
            # но для ясности и атомарности лучше, чтобы activate_version не делал commit, а возвращал результат.
            # Если activate_version делает commit, то все изменения до него (включая загрузку скидок) тоже будут закоммичены.
            # Давайте проверим activate_version.

            # В discount_service.py, activate_version ДЕЙСТВИТЕЛЬНО делает db.session.commit() в конце.
            # Это хорошо, значит, скидки, добавленные process_discounts_from_excel, будут закоммичены вместе со сменой активной версии.
            # Так что db.session.commit() здесь не нужен, если activate_version его делает.

            if email_data:
                send_email(email_data['subject'], email_data['html_body'])

            flash(
                f"Файл успешно загружен. Создана и активирована новая версия №{new_version.version_number} на основе файла. {result_message}",
                "success")
            return redirect(url_for('web.versions_index'))

        except Exception as e:
            db.session.rollback()
            flash(f"Произошла ошибка при обработке файла: {e}", "danger")
            return redirect(url_for('web.upload_discounts'))

    return render_template('upload.html', title='Загрузка скидок', form=form)


@web_bp.route('/discounts')
def discounts_overview():
    """
    Страница для отображения всей системы скидок.
    """
    discounts_data = get_discounts_with_summary()
    return render_template('discounts.html', title="Система скидок", structured_discounts=discounts_data)


@web_bp.route('/versions')
def versions_index():
    """Главная страница управления версиями."""
    versions = DiscountVersion.query.order_by(DiscountVersion.version_number.desc()).all()
    active_version_obj = next((v for v in versions if v.is_active), None)
    active_version_id = active_version_obj.id if active_version_obj else None

    latest_version_id = versions[0].id if versions else None

    return render_template(
        'versions.html',
        versions=versions,
        active_version_id=active_version_id,
        latest_version_id=latest_version_id,
        title="Версии скидок"
    )


@web_bp.route('/versions/view/<int:version_id>')
def view_version(version_id):
    """Страница просмотра конкретной версии в режиме 'только чтение'."""
    version = DiscountVersion.query.get_or_404(version_id)
    discounts = Discount.query.filter_by(version_id=version_id).order_by(Discount.complex_name, Discount.property_type,
                                                                         Discount.payment_method).all()

    return render_template(
        'view_version.html',
        version=version,
        discounts=discounts,
        title=f"Просмотр Версии №{version.version_number}"
    )


@web_bp.route('/versions/edit/<int:version_id>', methods=['GET', 'POST'])
def edit_version(version_id):
    """Страница редактирования конкретной версии."""
    latest_version = DiscountVersion.query.order_by(DiscountVersion.version_number.desc()).first()
    if not latest_version or version_id != latest_version.id:
        flash("Редактировать можно только самую последнюю версию скидок.", "warning")
        return redirect(url_for('web.versions_index'))

    version = DiscountVersion.query.get_or_404(version_id)

    if request.method == 'POST':
        changes_json = request.form.get('changes_json')
        if not changes_json:
            flash("Нет данных об изменениях для сохранения.", "warning")
            return redirect(url_for('web.edit_version', version_id=version_id))

        try:
            current_time_str = datetime.now().strftime('%Y-%m-%d %H:%M')
            new_version_comment = f"Обновление от {current_time_str}"

            new_version = create_new_version(comment=new_version_comment)

            new_version.changes_summary_json = changes_json

            update_discounts_for_version(new_version.id, request.form, changes_json)

            email_data = activate_version(new_version.id)
            if email_data:
                send_email(email_data['subject'], email_data['html_body'])

            flash(f"Изменения сохранены. Создана и активирована новая версия №{new_version.version_number}.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Произошла критическая ошибка при сохранении: {e}", "danger")

        return redirect(url_for('web.versions_index'))

    discounts = Discount.query.filter_by(version_id=version_id).order_by(Discount.complex_name, Discount.property_type,
                                                                         Discount.payment_method).all()

    comments_for_version = ComplexComment.query.filter_by(version_id=version_id).all()
    complex_comments = {c.complex_name: c.comment for c in comments_for_version}

    return render_template(
        'edit_version.html',
        version=version,
        discounts=discounts,
        complex_comments=complex_comments,
        title=f"Редактирование Версии №{version.version_number}"
    )


@web_bp.route('/versions/new', methods=['POST'])
def new_discount_version():
    """Создает новую версию вручную."""
    comment = request.form.get('comment', 'Новая версия без комментария.')
    new_version = create_new_version(comment)
    flash(f"Создана новая версия №{new_version.version_number}. Теперь вы можете ее отредактировать и активировать.",
          "success")
    return redirect(url_for('web.edit_version', version_id=new_version.id))


@web_bp.route('/versions/activate/<int:version_id>', methods=['POST'])
def activate_discount_version(version_id):
    """Активирует выбранную версию вручную."""
    email_data = activate_version(version_id)
    if email_data:
        send_email(email_data['subject'], email_data['html_body'])

    version = DiscountVersion.query.get(version_id)
    flash(f"Версия №{version.version_number} успешно активирована.", "success")
    return redirect(url_for('web.versions_index'))


@web_bp.route('/versions/comment/save', methods=['POST'])
def save_complex_comment():
    """Сохраняет комментарий к ЖК через AJAX."""
    data = request.get_json()
    version_id = data.get('version_id')
    complex_name = data.get('complex_name')
    comment_text = data.get('comment')

    if not all([version_id, complex_name]):
        return jsonify({'success': False, 'error': 'Missing data'}), 400

    comment = ComplexComment.query.filter_by(version_id=version_id, complex_name=complex_name).first()
    if not comment:
        comment = ComplexComment(version_id=version_id, complex_name=complex_name)
        db.session.add(comment)

    comment.comment = comment_text
    db.session.commit()

    return jsonify({'success': True})


@web_bp.route('/selection', methods=['GET', 'POST'])
def selection():
    """Страница для подбора квартир по бюджету."""
    results = None

    filter_options = get_filter_options()
    property_types = list(PropertyType)
    payment_methods = list(PaymentMethod)

    if request.method == 'POST':
        try:
            budget = float(request.form.get('budget'))
            currency = request.form.get('currency')
            prop_type_str = request.form.get('property_type')

            floor = request.form.get('floor')
            rooms = request.form.get('rooms')
            payment_method = request.form.get('payment_method')

            # --- ИСПРАВЛЕНИЕ: Передаем все параметры в сервис ---
            results = find_apartments_by_budget(
                budget,
                currency,
                prop_type_str,
                floor=floor,
                rooms=rooms,
                payment_method=payment_method
            )
        except (ValueError, TypeError):
            flash("Пожалуйста, введите корректную сумму бюджета.", "danger")

    return render_template('selection.html',
                           title="Подбор по бюджету",
                           results=results,
                           property_types=property_types,
                           filter_options=filter_options,
                           payment_methods=payment_methods
                           )


@web_bp.route('/apartment/<int:sell_id>')
def apartment_details(sell_id):
    """
    Страница с детальной информацией о конкретной квартире.
    """
    card_data = get_apartment_card_data(sell_id)

    all_discounts_data = card_data.pop('all_discounts_for_property_type', [])

    return render_template(
        'apartment_details.html',
        data=card_data,
        all_discounts_for_property_type=all_discounts_data,
        title=f"Детали объекта ID {sell_id}"
    )


@web_bp.route('/commercial-offer/<int:sell_id>')
def generate_commercial_offer(sell_id):
    """
    Генерирует коммерческое предложение для конкретного объекта.
    Получает актуальные цены из параметров запроса и курс USD с API ЦБ.
    """
    card_data = get_apartment_card_data(sell_id)

    passed_pricing = {}

    for option in card_data.get('pricing', []):
        payment_method = option['payment_method']

        final_price_key = f"fp_{payment_method}"
        final_price_str = request.args.get(final_price_key)

        initial_payment_key = f"ip_{payment_method}"
        initial_payment_str = request.args.get(initial_payment_key)

        base_price_deducted_key = f"bpd_{payment_method}"
        base_price_deducted_str = request.args.get(base_price_deducted_key)

        current_option_data = {
            'payment_method': payment_method,
            'base_price': option['base_price'],
            'deduction': option['deduction'],
            'price_after_deduction': float(base_price_deducted_str) if base_price_deducted_str else option[
                'price_after_deduction'],
            'final_price': float(final_price_str) if final_price_str else option['final_price'],
            'initial_payment': float(initial_payment_str) if initial_payment_str else None
        }
        passed_pricing[payment_method] = current_option_data

    updated_pricing_for_template = []
    for option_from_service in card_data.get('pricing', []):
        method = option_from_service['payment_method']
        if method in passed_pricing:
            updated_pricing_for_template.append(passed_pricing[method])
        else:
            updated_pricing_for_template.append(option_from_service)

    for method, data_from_passed in passed_pricing.items():
        if data_from_passed not in updated_pricing_for_template:
            updated_pricing_for_template.append(data_from_passed)

    card_data['pricing'] = updated_pricing_for_template

    current_date = datetime.now().strftime("%d.%m.%Y %H:%M")

    # --- НОВОЕ: Получаем актуальный курс USD ---
    usd_rate_from_cbu = get_current_usd_rate()
    # Если курс ЦБ не получен, используем захардкоженный из конфига как запасной вариант
    fallback_usd_rate = current_app.config.get('USD_TO_UZS_RATE', 12650.0)  # Запасной курс из config.py
    actual_usd_rate = usd_rate_from_cbu if usd_rate_from_cbu is not None else fallback_usd_rate
    print(
        f"[ROUTES] Итоговый курс USD для КП: {actual_usd_rate} (из ЦБ: {usd_rate_from_cbu}, запасной: {fallback_usd_rate})")
    # --- КОНЕЦ НОВОГО ---

    return render_template(
        'commercial_offer.html',
        data=card_data,
        current_date=current_date,
        usd_to_uzs_rate=actual_usd_rate,  # Передаем курс в шаблон
        title=f"КП по объекту ID {sell_id}"
    )


@web_bp.route('/exclusions', methods=['GET', 'POST'])
def manage_exclusions():
    if request.method == 'POST':
        action = request.form.get('action')
        sell_id_str = request.form.get('sell_id_to_manage')
        comment = request.form.get('comment', '').strip()

        if not sell_id_str:
            flash("ID квартиры не может быть пустым.", "danger")
            return redirect(url_for('web.manage_exclusions'))

        try:
            sell_id = int(sell_id_str)
        except ValueError:
            flash("ID квартиры должен быть числом.", "danger")
            return redirect(url_for('web.manage_exclusions'))

        if action == 'add':
            existing_exclusion = ExcludedSell.query.filter_by(sell_id=sell_id).first()
            if existing_exclusion:
                flash(f"Квартира с ID {sell_id} уже находится в списке исключений.", "warning")
            else:
                new_exclusion = ExcludedSell(sell_id=sell_id, comment=comment if comment else None)
                db.session.add(new_exclusion)
                db.session.commit()
                flash(f"Квартира с ID {sell_id} успешно добавлена в исключения.", "success")
        elif action == 'delete':
            exclusion_to_delete = ExcludedSell.query.filter_by(sell_id=sell_id).first()
            if exclusion_to_delete:
                db.session.delete(exclusion_to_delete)
                db.session.commit()
                flash(f"Квартира с ID {sell_id} успешно удалена из исключений.", "success")
            else:
                flash(f"Квартира с ID {sell_id} не найдена в списке исключений.", "warning")
        else:
            flash("Неизвестное действие.", "danger")

        return redirect(url_for('web.manage_exclusions'))

    # GET-запрос: отображаем список исключений
    excluded_sells = ExcludedSell.query.order_by(ExcludedSell.created_at.desc()).all()
    return render_template('manage_exclusions.html', excluded_sells=excluded_sells, title="Управление исключениями")