# init_database.py в корне проекта
from app import create_app
from app.services.initial_load_service import load_all_initial_data
from app.core.config import DevelopmentConfig

print("Начинаем полную инициализацию базы данных. Это следует делать только один раз!")
app = create_app(DevelopmentConfig)
with app.app_context():
    # is_initial_setup=True создаст все таблицы
    load_all_initial_data(is_initial_setup=True) 
print("Инициализация завершена.")