import os
from flask import Flask
from flask_login import LoginManager  # НОВОЕ
from .core.config import DevelopmentConfig
from .core.extensions import db
# ИЗМЕНЕНИЕ: импортируем новую модель
from .models import estate_models, discount_models, user_models
from .services import email_service

# НОВОЕ: создаем экземпляр LoginManager
login_manager = LoginManager()
# НОВОЕ: указываем на view для логина. 'web.login' - это blueprint 'web' и функция 'login'
login_manager.login_view = 'web.login'
login_manager.login_message = "Пожалуйста, войдите в систему для доступа к этой странице."
login_manager.login_message_category = "info"


def create_app(config_class=DevelopmentConfig):
    """
    Фабрика для создания и конфигурации экземпляра приложения Flask.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)
    db_path = os.path.join(app.instance_path, 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        print(f"Папка instance готова по пути: {app.instance_path}")
    except OSError as e:
        print(f"Ошибка при создании папки instance: {e}")

    # Инициализируем расширения
    db.init_app(app)
    login_manager.init_app(app) # НОВОЕ

    # Регистрируем роуты
    from .web.routes import web_bp
    app.register_blueprint(web_bp)

    return app

# НОВОЕ: функция для загрузки пользователя из сессии
@login_manager.user_loader
def load_user(user_id):
    return user_models.User.query.get(int(user_id))