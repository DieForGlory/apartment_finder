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
    Создает все таблицы, начальные роли, права доступа и пользователя 'admin'.
    """
    with app.app_context():
        print("\n--- [ОТЛАДКА] Начало функции setup_database ---")

        from app.models import (discount_models, estate_models, exclusion_models,
                                finance_models, user_models)

        print("--- [ОТЛАДКА] Все модели импортированы. Вызов db.create_all()... ---")
        db.create_all()
        print("--- [ОТЛАДКА] db.create_all() завершен. ---")

        print("--- [ОТЛАДКА] Проверка существования ролей... ---")
        if user_models.Role.query.count() == 0:
            print("--- [ОТЛАДКА] Ролей не найдено. Создание начальных ролей и прав... ---")

            permissions_map = {
                'view_selection': 'Просмотр системы подбора',
                'view_discounts': 'Просмотр активной системы скидок',
                'view_version_history': 'Просмотр истории версий скидок',
                # 'view_reports': 'Просмотр всех отчетов', # <-- УДАЛИТЕ ЭТУ СТРОКУ
                'view_plan_fact_report': 'Просмотр План-факт отчета',
                'view_inventory_report': 'Просмотр отчета по остаткам',
                'view_manager_report': 'Просмотр отчетов по менеджерам',
                'view_project_dashboard': 'Просмотр аналитики по проектам',
                'manage_discounts': 'Управление версиями скидок (создание, активация)',
                'manage_settings': 'Управление настройками (калькуляторы, курс)',
                'manage_users': 'Управление пользователями',
                'upload_data': 'Загрузка данных (планы и т.д.)',
            }

            # 2. Определяем роли и какие права им соответствуют
            roles_permissions = {
                'MPP': ['view_selection', 'view_discounts'],
                'MANAGER': [
                    'view_selection', 'view_discounts', 'view_version_history', 'manage_settings',
                    # --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
                    'view_plan_fact_report', 'view_inventory_report', 'view_manager_report', 'view_project_dashboard'
                ],
                'ADMIN': [
                    'view_selection', 'view_discounts', 'view_version_history', 'manage_discounts',
                    'manage_settings', 'manage_users', 'upload_data',
                    # --- ИЗМЕНЕНИЯ ЗДЕСЬ ---
                    'view_plan_fact_report', 'view_inventory_report', 'view_manager_report', 'view_project_dashboard'
                ]
            }

            all_permissions = {}
            for name, desc in permissions_map.items():
                p = user_models.Permission(name=name, description=desc)
                all_permissions[name] = p
                db.session.add(p)

            for role_name, permissions_list in roles_permissions.items():
                role = user_models.Role(name=role_name)
                db.session.add(role)
                for p_name in permissions_list:
                    if p_name in all_permissions:
                        role.permissions.append(all_permissions[p_name])

            db.session.commit()
            print("--- [ОТЛАДКА] Роли и права успешно созданы и сохранены в БД. ---")
        else:
            print("--- [ОТЛАДКА] Роли уже существуют. Пропускаем создание. ---")

        print("--- [ОТЛАДКА] Проверка существования пользователя 'admin'... ---")
        if user_models.User.query.filter_by(username='admin').first() is None:
            print("--- [ОТЛАДКА] Пользователь 'admin' не найден. Создание... ---")
            admin_role = user_models.Role.query.filter_by(name='ADMIN').first()
            if admin_role:
                # V-- ИСПРАВЛЕНИЕ ЗДЕСЬ --V
                admin_user = user_models.User(
                    username='admin',
                    role=admin_role,
                    full_name='Администратор Системы',  # Добавляем ФИО
                    email='d.plakhotnyi@gh.uz'  # Добавляем email
                )
                # A-------------------------A
                admin_user.set_password('admin')
                db.session.add(admin_user)
                db.session.commit()
                print("--- [ОТЛАДКА] Пользователь 'admin' успешно создан. ---")
            else:
                print("--- [ОТЛАДКА] КРИТИЧЕСКАЯ ОШИБКА: Роль ADMIN не найдена, не могу создать пользователя! ---")
        else:
            print("--- [ОТЛАДКА] Пользователь 'admin' уже существует. ---")

        print("--- [ОТЛАДКА] Функция setup_database завершена. ---\n")


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