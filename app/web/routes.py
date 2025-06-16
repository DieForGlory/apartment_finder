import os
from app.services.discount_service import process_discounts_from_excel, generate_discount_template_excel, get_discounts_with_summary
from werkzeug.utils import secure_filename
from .forms import UploadExcelForm
from app.services.discount_service import process_discounts_from_excel
from app.services.data_service import get_sells_with_house_info
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app, send_file

# Создаем Blueprint. 'web' - это имя, которое мы будем использовать для ссылки на эти роуты.
web_bp = Blueprint('web', __name__, template_folder='templates')


@web_bp.route('/download-template')
def download_template():
    """
    Генерирует и отдает пользователю для скачивания шаблон Excel.
    """
    # 1. Вызываем наш сервис для генерации файла в памяти
    excel_data_stream = generate_discount_template_excel()

    # 2. Отправляем файл пользователю
    return send_file(
        excel_data_stream,
        # Имя файла, которое увидит пользователь
        download_name='discount_template.xlsx',
        # Указываем, что файл нужно скачать, а не открывать в браузере
        as_attachment=True,
        # MIME-тип для современных Excel-файлов
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@web_bp.route('/')
def index():
    """
    Главная страница с таблицей и пагинацией.
    """
    # Получаем номер страницы из GET-параметра ?page=...
    # По умолчанию — страница 1. `type=int` для безопасности.
    page = request.args.get('page', 1, type=int)

    # Устанавливаем количество записей на странице
    PER_PAGE = 40

    # Вызываем обновленный сервис с параметрами пагинации
    sells_pagination = get_sells_with_house_info(page=page, per_page=PER_PAGE)

    if not sells_pagination:
        flash("Не удалось загрузить данные о продажах.", "danger")
        # Передаем пустой объект пагинации, чтобы избежать ошибок в шаблоне
        return render_template('index.html', title='Ошибка', sells_pagination=None)

    return render_template('index.html', title='Главная', sells_pagination=sells_pagination)


@web_bp.route('/upload-discounts', methods=['GET', 'POST'])
def upload_discounts():
    """
    Страница для загрузки файла со скидками.
    """
    form = UploadExcelForm()
    if form.validate_on_submit():
        f = form.excel_file.data
        filename = secure_filename(f.filename)

        # Создаем временную директорию для загрузок, если ее нет
        upload_folder = os.path.join(current_app.root_path, 'uploads')
        os.makedirs(upload_folder, exist_ok=True)
        file_path = os.path.join(upload_folder, filename)

        f.save(file_path)

        try:
            result_message = process_discounts_from_excel(file_path)
            flash(f"Файл успешно загружен и обработан. {result_message}", "success")
        except Exception as e:
            flash(f"Произошла ошибка при обработке файла: {e}", "danger")

        return redirect(url_for('web.index'))

    return render_template('upload.html', title='Загрузка скидок', form=form)
@web_bp.route('/discounts')
def discounts_overview():
    """
    Страница для отображения всей системы скидок.
    """
    # ... и вызываем новую функцию ...
    discounts_data = get_discounts_with_summary()
    return render_template('discounts.html', title="Система скидок", structured_discounts=discounts_data)
