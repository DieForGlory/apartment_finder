import os
from app import create_app
from app.core.config import DevelopmentConfig
from app.services.initial_load_service import refresh_estate_data_from_mysql
from app.core.extensions import db
from app.models.user_models import User, Role

app = create_app(DevelopmentConfig)

# Определяем путь к файлу-флагу
LOCK_FILE_PATH = os.path.join(app.instance_path, 'update.lock')


def setup_database():
    """
    Создает все таблицы и начального пользователя 'admin', если их нет.
    Эту функцию нужно вызывать до любых операций с БД.
    """
    with app.app_context():
        # 1. Создаем все недостающие таблицы
        print("[SETUP] 🚀 Создание таблиц базы данных...")
        # Убедимся, что все модели импортированы, чтобы SQLAlchemy их "увидел"
        from app.models import discount_models, estate_models, exclusion_models, finance_models, user_models
        db.create_all()
        print("[SETUP] ✔️ Таблицы успешно созданы или уже существуют.")

        # 2. Создаем администратора по умолчанию
        if User.query.filter_by(username='admin').first() is None:
            print("[SETUP] 👤 Создание пользователя 'admin'...")
            admin_user = User(username='admin', role=Role.ADMIN)
            admin_user.set_password('admin')
            db.session.add(admin_user)
            db.session.commit()
            print("[SETUP] ✔️ Пользователь 'admin' успешно создан.")
        else:
            print("[SETUP] ℹ️ Пользователь 'admin' уже существует.")


# Этот блок выполняется только один раз при запуске сервера
if os.environ.get('WERKZEUG_RUN_MAIN') is None:
    # --- ШАГ 1: Инициализация базы данных ---
    # Создаем таблицы и админа ПЕРЕД миграцией
    setup_database()

    # --- ШАГ 2: Обновление данных из MySQL ---
    # Оборачиваем процесс обновления в try...finally для управления файлом блокировки
    try:
        # Создаем файл-флаг перед началом обновления
        with open(LOCK_FILE_PATH, 'w') as f:
            f.write('locked')
        print(f"[UPDATE FLAG] Файл блокировки создан: {LOCK_FILE_PATH}")

        # Запускаем обновление данных
        with app.app_context():
            refresh_estate_data_from_mysql()
    finally:
        # Гарантированно удаляем файл-флаг после завершения или ошибки
        if os.path.exists(LOCK_FILE_PATH):
            os.remove(LOCK_FILE_PATH)
            print(f"[UPDATE FLAG] Файл блокировки удален.")


if __name__ == '__main__':
    print("[FLASK APP] 🚦 Запуск веб-сервера Flask...")
    app.run(host='0.0.0.0', port=5000, debug=True)