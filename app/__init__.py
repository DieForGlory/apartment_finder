# app/__init__.py
import os
from flask import Flask, request, render_template
from flask_login import LoginManager
from flask_apscheduler import APScheduler
from flask_cors import CORS
from flask_migrate import Migrate
import json
from datetime import date, datetime

from .core.config import DevelopmentConfig
from .core.extensions import db

# 1. Создаем экземпляр LoginManager один раз
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = "Пожалуйста, войдите в систему для доступа к этой странице."
login_manager.login_message_category = "info"


# Пользовательский кодировщик для преобразования дат в JSON
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        try:
            if isinstance(obj, (date, datetime)):
                return obj.isoformat()
            iterable = iter(obj)
        except TypeError:
            pass
        else:
            return list(iterable)
        return json.JSONEncoder.default(self, obj)


def create_app(config_class=DevelopmentConfig):
    """
    Фабрика для создания и конфигурации экземпляра приложения Flask.
    """
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class)

    # Инициализируем расширения
    CORS(app)
    db.init_app(app)
    Migrate(app, db)
    login_manager.init_app(app)
    app.json_encoder = CustomJSONEncoder

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError as e:
        print(f"Ошибка при создании папки instance: {e}")

    # Инициализация планировщика
    scheduler = APScheduler()
    scheduler.init_app(app)

    # --- ИЗМЕНЕНИЕ ЗДЕСЬ ---
    # Проверяем, что мы не в режиме отладки ИЛИ что мы в основном процессе reloader'а
    if not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true':
        scheduler.start()
        with app.app_context():
            # Добавление задачи в планировщик
            if not scheduler.get_job('update_cbu_rate_job'):
                scheduler.add_job(
                    id='update_cbu_rate_job',
                    func='app.services.currency_service:fetch_and_update_cbu_rate',
                    trigger='interval',
                    hours=1
                )
    # --- КОНЕЦ ИЗМЕНЕНИЯ ---

    with app.app_context():
        # 3. Импортируем все актуальные модули моделей
        from .models import auth_models, planning_models, estate_models, finance_models, exclusion_models, funnel_models, special_offer_models

        # Регистрация Blueprints
        from .web.main_routes import main_bp
        from .web.auth_routes import auth_bp
        from .web.discount_routes import discount_bp
        from .web.report_routes import report_bp
        from .web.complex_calc_routes import complex_calc_bp
        from .web.settings_routes import settings_bp
        from .web.api_routes import api_bp
        from .web.special_offer_routes import special_offer_bp

        app.register_blueprint(report_bp, url_prefix='/reports')
        app.register_blueprint(main_bp)
        app.register_blueprint(auth_bp)
        app.register_blueprint(discount_bp)
        app.register_blueprint(complex_calc_bp)
        app.register_blueprint(settings_bp)
        app.register_blueprint(api_bp, url_prefix='/api/v1')
        app.register_blueprint(special_offer_bp, url_prefix='/specials')

        # 4. Обновляем загрузчик пользователя для Flask-Login
        @login_manager.user_loader
        def load_user(user_id):
            # Используем auth_models для поиска пользователя
            return auth_models.User.query.get(int(user_id))

        # Добавление задачи в планировщик
        if not scheduler.get_job('update_cbu_rate_job'):
            scheduler.add_job(
                id='update_cbu_rate_job',
                func='app.services.currency_service:fetch_and_update_cbu_rate',
                trigger='interval',
                hours=1
            )

    @app.before_request
    def check_for_update():
        lock_file_path = os.path.join(app.instance_path, 'update.lock')
        if os.path.exists(lock_file_path) and request.endpoint != 'static':
            return render_template('standolone/update_in_progress.html')

    return app