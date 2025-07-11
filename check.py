# check_data.py
import os
from app import create_app
from app.core.config import DevelopmentConfig
from app.core.extensions import db
from app.models.funnel_models import EstateBuysStatusLog
from sqlalchemy import func

# Создаем экземпляр приложения, чтобы получить доступ к базе данных
app = create_app(DevelopmentConfig)

# Выполняем все внутри контекста приложения
with app.app_context():
    print("\n--- [ОТЛАДКА] Начинаем поиск записей... ---")

    # Искомый статус и подстатус
    target_custom_status = 'Визит состоялся '

    # 1. Формируем запрос
    query = db.session.query(EstateBuysStatusLog).filter(
        # Используем надежное регистронезависимое сравнение без учета пробелов,
        func.lower(func.trim(EstateBuysStatusLog.status_custom_to_name)) == target_custom_status.lower()
    )

    # 2. Получаем все найденные записи
    found_logs = query.all()

    # 3. Выводим результат
    if found_logs:
        print(f"\n✅ Найдено записей с подстатусом '{target_custom_status}': {len(found_logs)}\n")
        print("Первые 50 найденных записей:")
        print("-" * 50)
        for log in found_logs[:50]:
            print(
                f"ID лога: {log.id}, ID заявки: {log.estate_buy_id}, Дата: {log.log_date}, Статус: {log.status_to_name}, Подстатус: {log.status_custom_to_name}")
    else:
        print(f"\n❌ Не най' и подстатусом '{target_custom_status}'.")

    print("\n--- [ОТЛАДКА] Поиск завершен. ---")