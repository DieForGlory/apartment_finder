from datetime import date
from wtforms import StringField, SubmitField, TextAreaField, IntegerField, FloatField
from wtforms.validators import DataRequired, NumberRange
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from ..models.user_models import Role, User # НОВЫЙ ИМПОРТ
from wtforms import SelectField, IntegerField
class UploadExcelForm(FlaskForm):
    """Форма для загрузки Excel файла."""
    excel_file = FileField(
        'Выберите Excel-файл со скидками',
        validators=[DataRequired(message="Необходимо выбрать файл.")]
    )
    submit = SubmitField('Загрузить')

# --- НОВАЯ ФОРМА ДЛЯ СОЗДАНИЯ ПОЛЬЗОВАТЕЛЯ ---
class CreateUserForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired(), Length(min=4, max=64)])
    # Делаем выбор роли из Enum
    role = SelectField('Роль', coerce=lambda r: Role[r], choices=[(role.name, role.value) for role in Role])
    password = PasswordField('Пароль', validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField('Подтвердите пароль', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Создать пользователя')

    def validate_username(self, username):
        """Проверка, что имя пользователя еще не занято."""
        user = User.query.filter_by(username=username.data).first()
        if user:
            raise ValidationError('Это имя пользователя уже занято. Пожалуйста, выберите другое.')

# --- НОВАЯ ФОРМА ДЛЯ СМЕНЫ ПАРОЛЯ ---
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
    # Поля для указания периода, к которому относится план
    year = IntegerField('Год', validators=[DataRequired()], default=date.today().year)
    month = SelectField('Месяц', coerce=int, choices=[(i, f'{i:02d}') for i in range(1, 13)],
                        default=date.today().month)

    submit = SubmitField('Загрузить план')


class CalculatorSettingsForm(FlaskForm):
    """Форма для настроек калькуляторов."""
    standard_installment_whitelist = TextAreaField('ID квартир для обычной рассрочки (через запятую)')
    dp_installment_whitelist = TextAreaField('ID квартир для рассрочки на ПВ (через запятую)')
    dp_installment_max_term = IntegerField('Макс. срок рассрочки на ПВ (мес)', validators=[DataRequired(), NumberRange(min=1, max=36)])
    time_value_rate_annual = FloatField('Годовая ставка для коэфф. (%)', validators=[DataRequired(), NumberRange(min=0)])
    submit = SubmitField('Сохранить настройки')