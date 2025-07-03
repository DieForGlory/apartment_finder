# app/__init__.py

import os
from flask import Flask
from flask_login import LoginManager
from .core.config import DevelopmentConfig
from .core.extensions import db
from .models import user_models
from flask_apscheduler import APScheduler

# Создаем экземпляр LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
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

    # Инициализация планировщика
    scheduler = APScheduler()
    scheduler.init_app(app)
    scheduler.start()

    # Добавление задачи через СТРОКОВЫЙ ПУТЬ для избежания циклического импорта
    if not scheduler.get_job('update_cbu_rate_job'):
        scheduler.add_job(
            id='update_cbu_rate_job',
            func='app.services.currency_service:fetch_and_update_cbu_rate',
            trigger='interval',
            hours=1
        )

    try:
        os.makedirs(app.instance_path, exist_ok=True)
        print(f"Папка instance готова по пути: {app.instance_path}")
    except OSError as e:
        print(f"Ошибка при создании папки instance: {e}")

    # Инициализируем расширения
    db.init_app(app)
    login_manager.init_app(app)

    # Регистрация Blueprints
    from .web.main_routes import main_bp
    from .web.auth_routes import auth_bp
    from .web.discount_routes import discount_bp
    from .web.report_routes import report_bp
    from .web.complex_calc_routes import complex_calc_bp
    from .web.settings_routes import settings_bp
    app.register_blueprint(report_bp, url_prefix='/reports')
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(discount_bp)
    app.register_blueprint(complex_calc_bp)
    app.register_blueprint(settings_bp)

    return app


@login_manager.user_loader
def load_user(user_id):
    return user_models.User.query.get(int(user_id))