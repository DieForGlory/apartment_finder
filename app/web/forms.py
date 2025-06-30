from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, FileField, SelectField
from wtforms.validators import DataRequired, Length, EqualTo, ValidationError
from ..models.user_models import Role, User # НОВЫЙ ИМПОРТ

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