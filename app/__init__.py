import os
from flask import Flask
from .core.config import DevelopmentConfig
from .core.extensions import db
from .models import estate_models, discount_models
from .models import estate_models, discount_models
from .services import email_service

def create_app(config_class=DevelopmentConfig):
    """
    Фабрика для создания и конфигурации экземпляра приложения Flask.
    """
    # instance_relative_config=True — ключ к использованию папки instance
    app = Flask(__name__, instance_relative_config=True)

    # 1. Загружаем базовую конфигурацию (БЕЗ пути к БД)
    app.config.from_object(config_class)

    # 2. ФОРМИРУЕМ ПРАВИЛЬНЫЙ ПУТЬ К БД И ЗАДАЕМ ЕГО
    # Это самый надежный способ указать путь к файлу БД
    db_path = os.path.join(app.instance_path, 'app.db')
    app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

    # 3. ЯВНО СОЗДАЕМ ПАПКУ INSTANCE ПЕРЕД ИНИЦИАЛИЗАЦИЕЙ БД
    # Это гарантирует, что директория для файла БД существует
    try:
        os.makedirs(app.instance_path, exist_ok=True)
        print(f"Папка instance готова по пути: {app.instance_path}")
    except OSError as e:
        print(f"Ошибка при создании папки instance: {e}")

    # 4. Инициализируем расширения
    db.init_app(app)

    # 5. Регистрируем роуты
    from .web.routes import web_bp
    app.register_blueprint(web_bp)

    return app