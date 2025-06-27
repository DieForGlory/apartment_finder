import os
from app import create_app
from app.core.config import DevelopmentConfig
from app.services.initial_load_service import load_all_initial_data
from app.models import exclusion_models
# Создаем экземпляр приложения Flask
app = create_app(DevelopmentConfig)

# --- НАЧАЛО БЛОКА ПРЕДВАРИТЕЛЬНОЙ ЗАГРУЗКИ ---

# Эта проверка гарантирует, что код внутри выполнится только ОДИН РАЗ
# в основном процессе, а не в дочернем процессе-перезагрузчике.
if os.environ.get('WERKZEUG_RUN_MAIN') is None:
    # Выполняем загрузку данных в контексте нашего приложения
    with app.app_context():
        load_all_initial_data()

# --- КОНЕЦ БЛОКА ---


if __name__ == '__main__':
    # Запускаем веб-сервер только ПОСЛЕ того, как загрузка данных завершена
    print("[FLASK APP] 🚦 Запуск веб-сервера Flask...")
    app.run(host='0.0.0.0', port=5000)