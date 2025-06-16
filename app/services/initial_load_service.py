import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask import current_app

from ..core.extensions import db
from ..models.estate_models import EstateHouse, EstateSell
from .discount_service import process_discounts_from_excel

# Путь к файлу скидок остается
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
DISCOUNTS_EXCEL_PATH = os.path.join(PROJECT_ROOT, 'data_sources', 'discounts_template.xlsx')


def _migrate_mysql_to_sqlite():
    """
    Подключается к MySQL, извлекает данные и готовит их для записи в SQLite.
    """
    print("[MIGRATE] 🔄 Начало миграции данных из MySQL в SQLite...")

    mysql_uri = current_app.config['SOURCE_MYSQL_URI']
    mysql_engine = create_engine(mysql_uri)
    MySQLSession = sessionmaker(bind=mysql_engine)
    mysql_session = MySQLSession()

    try:
        # ... (миграция estate_houses без изменений)
        print("[MIGRATE] 🏡 Загрузка данных из таблицы 'estate_houses'...")
        mysql_houses = mysql_session.query(EstateHouse).all()
        for house in mysql_houses:
            new_house = EstateHouse(
                id=house.id,
                complex_name=house.complex_name,
                name=house.name,
                geo_house=house.geo_house
            )
            db.session.add(new_house)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи домов: {len(mysql_houses)}")

        # 2. Миграция таблицы estate_sells
        print("[MIGRATE]  квартир Загрузка данных из таблицы 'estate_sells'...")
        mysql_sells = mysql_session.query(EstateSell).all()
        for sell in mysql_sells:
            new_sell = EstateSell(
                id=sell.id,
                house_id=sell.house_id,
                estate_sell_category=sell.estate_sell_category,
                estate_floor=sell.estate_floor,
                estate_rooms=sell.estate_rooms,
                estate_price_m2=sell.estate_price_m2,
                estate_sell_status_name=sell.estate_sell_status_name,
                estate_price=sell.estate_price,
                # --- ДОБАВЛЯЕМ МИГРАЦИЮ ПЛОЩАДИ ---
                estate_area=sell.estate_area
            )
            db.session.add(new_sell)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи объектов продажи: {len(mysql_sells)}")

    except Exception as e:
        print(f"[MIGRATE] ❌ ОШИБКА во время миграции: {e}")
    finally:
        mysql_session.close()
        print("[MIGRATE] 🔌 Соединение с MySQL закрыто.")


def load_all_initial_data():
    """
    Полностью очищает локальную БД и наполняет её данными из MySQL и Excel.
    """
    print("\n[INITIAL LOAD] 🚀 НАЧАЛО ПРОЦЕССА ПЕРВОНАЧАЛЬНОЙ ЗАГРУЗКИ ДАННЫХ...")

    db.drop_all()
    db.create_all()

    _migrate_mysql_to_sqlite()

    if os.path.exists(DISCOUNTS_EXCEL_PATH):
        print(f"[INITIAL LOAD] 📥 Загрузка скидок из файла: {DISCOUNTS_EXCEL_PATH}")
        process_discounts_from_excel(DISCOUNTS_EXCEL_PATH)
    else:
        print(f"[INITIAL LOAD] ⚠️  ВНИМАНИЕ: Файл со скидками не найден. Пропускаем шаг.")

    try:
        print("[INITIAL LOAD] 💾 Сохранение всех данных в локальную БД (SQLite)...")
        db.session.commit()
        print("[INITIAL LOAD] ✔️ Все данные успешно сохранены.")
    except Exception as e:
        print(f"[INITIAL LOAD] ❌ Ошибка при сохранении данных в БД: {e}")
        db.session.rollback()

    print("[INITIAL LOAD] ✅ ПРОЦЕСС ПЕРВОНАЧАЛЬНОЙ ЗАГРУЗКИ ЗАВЕРШЕН.\n")
