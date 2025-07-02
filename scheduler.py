import time
from app import create_app
from app.core.config import DevelopmentConfig
from app.services.initial_load_service import refresh_estate_data_from_mysql
from datetime import datetime

# Создаем экземпляр приложения Flask, чтобы получить доступ к его контексту
app = create_app(DevelopmentConfig)

# Интервал в секундах (75 минут * 60 секунд)
SLEEP_INTERVAL = 75 * 60


def run_scheduler():
    """
    Бесконечный цикл, который запускает обновление данных каждые 75 минут.
    """
    print("--- [ПЛАНИРОВЩИК ЗАПУЩЕН] ---")
    while True:
        print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Начинаю обновление данных из MySQL...")

        try:
            # Используем контекст приложения, чтобы сервис мог работать с базой данных
            with app.app_context():
                refresh_estate_data_from_mysql()

            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ✔️ Обновление успешно завершено.")

        except Exception as e:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] ❌ ОШИБКА во время обновления: {e}")

        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Следующее обновление через 75 минут...")
        time.sleep(SLEEP_INTERVAL)


if __name__ == '__main__':
    run_scheduler()