import os
import json
from ..models.discount_models import PropertyType, PaymentMethod
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file, jsonify
from ..models.user_models import User, Role
from flask_login import login_user, logout_user, login_required, current_user
from ..models.exclusion_models import ExcludedSell
from ..services import discount_service
from ..services.selection_service import find_apartments_by_budget, get_apartment_card_data
from ..core.extensions import db
from .forms import UploadExcelForm, CreateUserForm, ChangePasswordForm
from ..core.decorators import role_required
from ..services.data_service import get_sells_with_house_info, get_filter_options
from ..services.email_service import send_email
from ..services.discount_service import (
    process_discounts_from_excel,
    generate_discount_template_excel,
    get_discounts_with_summary,
    create_blank_version,
    delete_draft_version,
    activate_version,
    update_discounts_for_version, get_current_usd_rate
)
from ..models.discount_models import Discount, DiscountVersion, ComplexComment

# Создаем Blueprint. 'web' - это имя, которое мы будем использовать для ссылки на эти роуты.
web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/versions/delete/<int:version_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def delete_version(version_id):
    try:
        delete_draft_version(version_id)
        flash(f"Черновик версии успешно удален.", "success")
    except ValueError as e:
        flash(str(e), "danger")
    except PermissionError as e:
        flash(str(e), "danger")
    except Exception as e:
        flash(f"Произошла неизвестная ошибка при удалении: {e}", "danger")

    return redirect(url_for('web.versions_index'))

@web_bp.route('/download-template')
@login_required
@role_required('ADMIN')
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
@login_required
@role_required('ADMIN', 'MANAGER')
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
@login_required
@role_required('ADMIN')
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
@login_required
@role_required('ADMIN', 'MANAGER', 'MPP')
def discounts_overview():
    """
    Страница для отображения всей системы скидок.
    """
    discounts_data = get_discounts_with_summary()
    return render_template('discounts.html', title="Система скидок", structured_discounts=discounts_data)


@web_bp.route('/versions')
@login_required
@role_required('ADMIN', 'MANAGER')
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
@login_required
@role_required('ADMIN', 'MANAGER')
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
@login_required
@role_required('ADMIN')
def edit_version(version_id):
    version = DiscountVersion.query.get_or_404(version_id)
    if version.is_active:
        flash('Активные версии нельзя редактировать. Создайте новый черновик.', 'warning')
        return redirect(url_for('web.versions_index'))

    version = DiscountVersion.query.get_or_404(version_id)

    if request.method == 'POST':
        # Этот код будет вызван при сохранении изменений в черновике
        changes_json = request.form.get('changes_json')
        if not changes_json:
            flash("Нет данных об изменениях для сохранения.", "warning")
            return redirect(url_for('web.edit_version', version_id=version_id))

        try:
            # Вызываем наш обновленный сервис, который сохранит изменения в текущем черновике
            # и перезапишет саммари.
            result_message = update_discounts_for_version(version_id, request.form, changes_json)

            # Просто сообщаем, что черновик обновлен. НЕ активируем и НЕ отправляем email.
            flash(f"Изменения в черновике версии №{version.version_number} успешно сохранены.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Произошла критическая ошибка при сохранении: {e}", "danger")

        # Возвращаем пользователя на страницу со списком всех версий
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



@web_bp.route('/versions/create-draft', methods=['POST'])
@login_required
@role_required('ADMIN')
def create_draft_version():
    active_version = DiscountVersion.query.filter_by(is_active=True).first()
    if not active_version:
        flash('Не найдена активная версия для создания черновика.', 'danger')
        return redirect(url_for('web.versions_index'))

    try:
        draft_version = discount_service.clone_version_for_editing(active_version)
        flash(f'Создан новый черновик версии №{draft_version.version_number}. Теперь вы можете внести изменения.',
              'success')
        return redirect(url_for('web.edit_version', version_id=draft_version.id))
    except Exception as e:
        flash(f'Ошибка при создании черновика: {e}', 'danger')
        return redirect(url_for('web.versions_index'))


web_bp.route('/versions/activate/<int:version_id>', methods=['POST'])


@web_bp.route('/versions/activate/<int:version_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def activate_discount_version(version_id):
    # Получаем новый комментарий из формы модального окна
    activation_comment = request.form.get('comment')
    if not activation_comment:
        flash("Название (комментарий) для системы скидок не может быть пустым.", "warning")
        return redirect(url_for('web.versions_index'))

    try:
        email_data = activate_version(version_id, activation_comment=activation_comment)
        if email_data:
            send_email(email_data['subject'], email_data['html_body'])

        version = DiscountVersion.query.get(version_id)
        flash(f"Версия №{version.version_number} успешно активирована.", "success")
    except Exception as e:
        flash(f"Ошибка при активации: {e}", "danger")

    return redirect(url_for('web.versions_index'))


@web_bp.route('/users/delete/<int:user_id>', methods=['POST'])
@login_required
@role_required('ADMIN')
def delete_user(user_id):
    if user_id == current_user.id:
        flash('Вы не можете удалить свою учетную запись.', 'danger')
        return redirect(url_for('web.user_management'))

    user_to_delete = User.query.get_or_404(user_id)
    db.session.delete(user_to_delete)
    db.session.commit()
    flash(f'Пользователь {user_to_delete.username} удален.', 'success')
    return redirect(url_for('web.user_management'))


@web_bp.route('/change-password', methods=['GET', 'POST'])
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
            return redirect(url_for('web.selection'))

    return render_template('change_password.html', title="Смена пароля", form=form)

@web_bp.route('/users', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
def user_management():
    form = CreateUserForm()
    if form.validate_on_submit():
        user = User(
            username=form.username.data,
            role=form.role.data
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash(f'Пользователь {user.username} успешно создан.', 'success')
        return redirect(url_for('web.user_management'))

    users = User.query.order_by(User.id).all()
    return render_template('user_management.html', title="Управление пользователями", users=users, form=form)
@web_bp.route('/versions/comment/save', methods=['POST'])
@login_required
@role_required('ADMIN')
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
@login_required
@role_required('ADMIN', 'MANAGER', 'MPP')
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
@login_required
@role_required('ADMIN', 'MANAGER', 'MPP')
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
@login_required
@role_required('ADMIN', 'MANAGER', 'MPP')
def generate_commercial_offer(sell_id):
    """
    Генерирует КП. Пересчитывает все цены на сервере на основе выбранных скидок.
    """
    # 1. Получаем базовые данные по квартире и всем возможным скидкам
    card_data = get_apartment_card_data(sell_id)
    if not card_data.get('apartment'):
        return "Apartment not found", 404

    # 2. Получаем JSON с выбранными пользователем скидками из URL
    selections_json = request.args.get('selections', '{}')
    try:
        user_selections = json.loads(selections_json)
    except json.JSONDecodeError:
        user_selections = {}

    # 3. Пересчитываем все варианты оплаты на сервере
    updated_pricing_for_template = []
    base_options = card_data.get('pricing', [])
    all_discounts = card_data.get('all_discounts_for_property_type', [])

    for option in base_options:
        type_key = option['type_key']
        base_price_deducted = option['price_after_deduction']

        # Начинаем с базовых скидок (МПП, РОП)
        total_discount_rate = sum(d['value'] for d in option.get('discounts', []))

        applied_discounts_details = []
        for disc in option.get('discounts', []):
            applied_discounts_details.append({
                'name': disc['name'],
                'amount': base_price_deducted * disc['value']
            })

        # Ищем объект скидок для этого типа оплаты
        base_payment_method_value = '100% оплата' if '100' in type_key or 'full_payment' in type_key else 'Ипотека'
        discount_object = next((d for d in all_discounts if d['payment_method'] == base_payment_method_value), None)

        # Применяем дополнительные скидки, выбранные пользователем
        if type_key in user_selections and discount_object:
            for disc_name, disc_percent in user_selections[type_key].items():
                server_percent = discount_object.get(disc_name, 0) * 100
                # Убедимся, что пользователь не подделал процент скидки
                if abs(float(disc_percent) - server_percent) < 0.01:
                    rate_to_add = server_percent / 100.0
                    total_discount_rate += rate_to_add
                    applied_discounts_details.append({
                        'name': disc_name.upper(),
                        'amount': base_price_deducted * rate_to_add
                    })

        # Пересчитываем финальную цену и ПВ на основе итоговой ставки
        final_price = base_price_deducted * (1 - total_discount_rate)
        initial_payment = None

        if 'mortgage' in type_key:
            from ..services.selection_service import MAX_MORTGAGE, MIN_INITIAL_PAYMENT_PERCENT
            initial_payment = final_price - MAX_MORTGAGE
            min_req_payment = final_price * MIN_INITIAL_PAYMENT_PERCENT
            if initial_payment < 0: initial_payment = 0
            if initial_payment < min_req_payment: initial_payment = min_req_payment
            final_price = initial_payment + MAX_MORTGAGE

        # Собираем итоговый объект для шаблона
        option['final_price'] = final_price
        option['initial_payment'] = initial_payment
        option['applied_discounts'] = applied_discounts_details
        updated_pricing_for_template.append(option)

    card_data['pricing'] = updated_pricing_for_template

    # Получаем курс валют и дату
    current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
    usd_rate_from_cbu = get_current_usd_rate()
    fallback_usd_rate = current_app.config.get('USD_TO_UZS_RATE', 12650.0)
    actual_usd_rate = usd_rate_from_cbu if usd_rate_from_cbu is not None else fallback_usd_rate

    return render_template(
        'commercial_offer.html',
        data=card_data,
        current_date=current_date,
        usd_to_uzs_rate=actual_usd_rate,
        title=f"КП по объекту ID {sell_id}"
    )


@web_bp.route('/exclusions', methods=['GET', 'POST'])
@login_required
@role_required('ADMIN')
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
@web_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('web.selection')) # Если уже вошел, перенаправляем

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            # Перенаправление на страницу, которую пользователь пытался открыть
            next_page = request.args.get('next')
            return redirect(next_page or url_for('web.selection'))
        else:
            flash('Неверный логин или пароль.', 'danger')

    return render_template('login.html', title='Вход в систему')

# НОВЫЙ РОУТ для выхода
@web_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы успешно вышли из системы.', 'success')
    return redirect(url_for('web.login'))