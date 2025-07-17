# forms.py

from datetime import date
from flask_wtf import FlaskForm
from wtforms import (StringField, PasswordField, SubmitField, FileField, SelectField,
                     SelectMultipleField, TextAreaField, IntegerField, FloatField)
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError, Email, NumberRange
from wtforms.widgets import CheckboxInput
from wtforms import FileField, TextAreaField, FloatField
# --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
# Импортируем сам модуль auth_models
from ..models import auth_models
from wtforms.validators import Optional

class UploadExcelForm(FlaskForm):
    """Форма для загрузки Excel файла."""
    excel_file = FileField(
        'Выберите Excel-файл со скидками',
        validators=[DataRequired(message="Необходимо выбрать файл.")]
    )
    submit = SubmitField('Загрузить')


class CreateUserForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=64)])
    full_name = StringField('ФИО', validators=[DataRequired()])
    email = StringField('Email', validators=[DataRequired(), Email(message="Некорректный email адрес.")])
    phone_number = StringField('Номер телефона (опционально)')
    role = SelectField('Роль', coerce=int, validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Создать пользователя')

    def validate_username(self, username):
        """Проверка, что имя пользователя еще не занято."""
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        if auth_models.User.query.filter_by(username=username.data).first():
            raise ValidationError('Это имя пользователя уже занято.')

    def validate_email(self, email):
        """Проверка, что email еще не занят."""
        # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
        if auth_models.User.query.filter_by(email=email.data).first():
            raise ValidationError('Этот email уже зарегистрирован.')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Текущий пароль', validators=[DataRequired()])
    new_password = PasswordField('Новый пароль', validators=[DataRequired(), Length(min=6)])
    confirm_new_password = PasswordField('Подтвердите новый пароль', validators=[DataRequired(), EqualTo('new_password')])
    submit = SubmitField('Сменить пароль')


class UploadPlanForm(FlaskForm):
    """Форма для загрузки Excel файла с планами."""
    excel_file = FileField(
        'Выберите Excel-файл с планами',
        validators=[DataRequired(message="Необходимо выбрать файл.")]
    )
    year = IntegerField('Год', validators=[DataRequired()], default=date.today().year)
    month = SelectField('Месяц', coerce=int, choices=[(i, f'{i:02d}') for i in range(1, 13)],
                        default=date.today().month)
    submit = SubmitField('Загрузить план')


class CalculatorSettingsForm(FlaskForm):
    """Форма для настроек калькуляторов."""
    standard_installment_whitelist = TextAreaField('ID квартир для обычной рассрочки (через запятую)')
    dp_installment_whitelist = TextAreaField('ID квартир для рассрочки на ПВ (через запятую)')
    dp_installment_max_term = IntegerField('Макс. срок рассрочки на ПВ (мес)',
                                           validators=[DataRequired(), NumberRange(min=1, max=36)])
    time_value_rate_annual = FloatField('Годовая ставка для коэфф. (%)',
                                        validators=[DataRequired(), NumberRange(min=0)])
    standard_installment_min_dp_percent = FloatField(
        'Мин. ПВ для стандартной рассрочки (%)',
        validators=[DataRequired(message="Это поле обязательно."), NumberRange(min=0, max=100)],
        default=15.0
    )
    submit = SubmitField('Сохранить настройки')


class UploadManagerPlanForm(FlaskForm):
    """Форма для загрузки Excel файла с планами менеджеров."""
    excel_file = FileField(
        'Выберите Excel-файл с планами',
        validators=[DataRequired(message="Необходимо выбрать файл.")]
    )
    submit = SubmitField('Загрузить планы')


class RoleForm(FlaskForm):
    """Форма для создания и редактирования ролей."""
    name = StringField('Название роли', validators=[DataRequired(), Length(min=2, max=80)])
    permissions = SelectMultipleField(
        'Разрешения для роли',
        coerce=int,
        widget=CheckboxInput()
    )
    submit = SubmitField('Сохранить')

class MonthlySpecialForm(FlaskForm):
    """Форма для добавления/редактирования 'Квартиры месяца'."""
    sell_id = IntegerField('ID Квартиры (из estate_sells)', validators=[DataRequired(message="ID квартиры обязателен.")])
    usp_text = TextAreaField('УТП (Уникальное Торговое Предложение)', validators=[DataRequired(message="Укажите УТП.")])
    extra_discount = FloatField('Дополнительная скидка (%)', validators=[DataRequired(), NumberRange(min=0, max=50)])
    floor_plan_image = FileField('Файл с планировкой (png, jpg, svg, webp)', validators=[DataRequired(message="Загрузите планировку.")])
    submit = SubmitField('Добавить предложение')

class EditMonthlySpecialForm(FlaskForm):
    """Форма для РЕДАКТИРОВАНИЯ 'Квартиры месяца'."""
    usp_text = TextAreaField('УТП (Уникальное Торговое Предложение)', validators=[DataRequired(message="Укажите УТП.")])
    extra_discount = FloatField('Дополнительная скидка (%)', validators=[DataRequired(), NumberRange(min=0, max=50)])
    # Делаем поле файла необязательным
    floor_plan_image = FileField('Загрузить НОВУЮ планировку (необязательно)', validators=[Optional()])
    submit = SubmitField('Сохранить изменения')