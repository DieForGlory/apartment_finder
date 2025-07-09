import enum
from app.core.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Role(enum.Enum):
    ADMIN = 'Администратор'
    MANAGER = 'Руководитель'
    MPP = 'МПП'

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    __bind_key__ = 'discounts'  # Храним пользователей в той же БД, что и скидки

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True, nullable=False)
    password_hash = db.Column(db.String(256))
    role = db.Column(db.Enum(Role), default=Role.MPP, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

class SalesManager(db.Model):
    """Модель для хранения данных о менеджерах по продажам из внешней БД."""
    __tablename__ = 'sales_managers'
    # Используем тот же bind_key, так как эти данные тесно связаны со скидками и отчетами
    __bind_key__ = 'discounts'

    id = db.Column(db.Integer, primary_key=True) # Это будет id из MySQL
    full_name = db.Column(db.String(255), unique=True, nullable=False)

    def __repr__(self):
        return f'<SalesManager {self.full_name}>'