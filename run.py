import os
from app import create_app
from app.core.config import DevelopmentConfig
from app.services.initial_load_service import refresh_estate_data_from_mysql
# НОВЫЕ ИМПОРТЫ
from app.core.extensions import db
from app.models.user_models import User, Role

app = create_app(DevelopmentConfig)

def create_initial_admin():
    """Создает пользователя 'admin', если он не существует."""
    with app.app_context():
        # Перед созданием таблиц, убедимся что все модели импортированы
        from app.models import discount_models, estate_models, exclusion_models
        db.create_all() # Создаем все таблицы, включая 'users'

        if User.query.filter_by(username='admin').first() is None:
            print("[SETUP] 👤 Создание пользователя 'admin'...")
            admin_user = User(username='admin', role=Role.ADMIN)
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            print("[SETUP] ✔️ Пользователь 'admin' успешно создан.")
        else:
            print("[SETUP] ℹ️ Пользователь 'admin' уже существует.")

if os.environ.get('WERKZEUG_RUN_MAIN') is None:
    with app.app_context():
        refresh_estate_data_from_mysql()
    # НОВЫЙ ВЫЗОВ
    create_initial_admin()


if __name__ == '__main__':
    print("[FLASK APP] 🚦 Запуск веб-сервера Flask...")
    app.run(host='0.0.0.0', port=5000)