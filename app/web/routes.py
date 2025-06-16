import os
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file

from ..core.extensions import db
from .forms import UploadExcelForm
from ..services.data_service import get_sells_with_house_info
from ..services.discount_service import (
    process_discounts_from_excel,
    generate_discount_template_excel,
    get_discounts_with_summary,
    create_new_version,
    activate_version,
    update_discounts_for_version
)
from ..models.discount_models import Discount, DiscountVersion

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
    Создает новую версию и делает ее активной.
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
            # 1. Сначала создаем новую версию, используя имя файла как комментарий
            comment = f"Загрузка из файла: {filename}"
            new_version = create_new_version(comment=comment)

            # 2. Обрабатываем Excel, привязывая скидки к ID новой версии
            result_message = process_discounts_from_excel(file_path, new_version.id)
            db.session.commit()

            # 3. Активируем новую версию
            activate_version(new_version.id)

            flash(
                f"Файл успешно загружен. Создана и активирована новая версия №{new_version.version_number}. {result_message}",
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


# --- НОВЫЕ МАРШРУТЫ ДЛЯ УПРАВЛЕНИЯ ВЕРСИЯМИ ---

@web_bp.route('/versions')
def versions_index():
    """Главная страница управления версиями."""
    versions = DiscountVersion.query.order_by(DiscountVersion.version_number.desc()).all()
    active_version_obj = next((v for v in versions if v.is_active), None)
    active_version_id = active_version_obj.id if active_version_obj else None

    # Находим ID самой последней версии
    latest_version_id = versions[0].id if versions else None

    return render_template(
        'versions.html',
        versions=versions,
        active_version_id=active_version_id,
        latest_version_id=latest_version_id,  # <-- Передаем ID в шаблон
        title="Версии скидок"
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
        # Получаем комментарий из формы
        comment = request.form.get('changes_comment', 'Изменения без комментария.')
        # Передаем комментарий в сервисную функцию
        result_message = update_discounts_for_version(version_id, request.form, comment)
        flash(result_message, "info")
        return redirect(url_for('web.edit_version', version_id=version_id))

    discounts = Discount.query.filter_by(version_id=version_id).order_by(Discount.complex_name, Discount.property_type,
                                                                         Discount.payment_method).all()

    return render_template(
        'edit_version.html',
        version=version,
        discounts=discounts,
        title=f"Редактирование Версии №{version.version_number}"
    )

@web_bp.route('/versions/new', methods=['POST'])
def new_discount_version():
    """Создает новую версию."""
    comment = request.form.get('comment', 'Новая версия без комментария.')
    new_version = create_new_version(comment)
    flash(f"Создана новая версия №{new_version.version_number}. Теперь вы можете ее отредактировать и активировать.",
          "success")
    # Перенаправляем сразу на страницу редактирования новой версии
    return redirect(url_for('web.edit_version', version_id=new_version.id))


@web_bp.route('/versions/activate/<int:version_id>', methods=['POST'])
def activate_discount_version(version_id):
    """Активирует выбранную версию."""
    activate_version(version_id)
    version = DiscountVersion.query.get(version_id)
    flash(f"Версия №{version.version_number} успешно активирована.", "success")
    return redirect(url_for('web.versions_index'))

# --- КОНЕЦ НОВЫХ МАРШРУТОВ ---