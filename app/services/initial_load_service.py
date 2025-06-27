import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from flask import current_app

from ..core.extensions import db
from ..models.estate_models import EstateHouse, EstateSell
from ..models.discount_models import DiscountVersion, Discount # Ensure Discount is imported if needed for clearing
from ..models.exclusion_models import ExcludedSell # Ensure ExcludedSell is imported if needed for clearing
from .discount_service import process_discounts_from_excel

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
DISCOUNTS_EXCEL_PATH = os.path.join(PROJECT_ROOT, 'data_sources', 'discounts_template.xlsx')


def _migrate_mysql_estate_data_to_sqlite():
    """
    Подключается к MySQL, извлекает данные по недвижимости (дома, квартиры)
    и перезаписывает их в SQLite.
    НЕ затрагивает таблицы скидок или исключений.
    """
    print("[MIGRATE] 🔄 Начало миграции данных недвижимости из MySQL в SQLite...")

    mysql_uri = current_app.config['SOURCE_MYSQL_URI']
    mysql_engine = create_engine(mysql_uri)
    MySQLSession = sessionmaker(bind=mysql_engine)
    mysql_session = MySQLSession()

    try:
        # Очищаем только данные по недвижимости в SQLite перед новой миграцией
        print("[MIGRATE] 🧹 Очистка существующих данных по недвижимости в SQLite (EstateHouse, EstateSell)...")
        db.session.query(EstateSell).delete()
        db.session.query(EstateHouse).delete()
        db.session.commit() # Commit the deletion
        print("[MIGRATE] ✔️ Данные по недвижимости очищены.")

        # 1. Миграция таблицы estate_houses
        print("[MIGRATE] 🏡 Загрузка данных из таблицы 'estate_houses'...")
        mysql_houses = mysql_session.query(EstateHouse).filter(EstateHouse.complex_name.isnot(None)).all()
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
        print("[MIGRATE] 🏢 Загрузка данных из таблицы 'estate_sells'...")
        mysql_sells = mysql_session.query(EstateSell).all()
        ESTATE_SELL_CATEGORY_MAPPING = {
            'flat': 'Квартира',
            'comm': 'Коммерческое помещение',
            'garage': 'Парковка',
            'storageroom': 'Кладовое помещение',
        }
        for sell in mysql_sells:
            new_sell = EstateSell(
                id=sell.id,
                house_id=sell.house_id,
                estate_sell_category=ESTATE_SELL_CATEGORY_MAPPING.get(sell.estate_sell_category, sell.estate_sell_category),
                estate_floor=sell.estate_floor,
                estate_rooms=sell.estate_rooms,
                estate_price_m2=sell.estate_price_m2,
                estate_sell_status_name=sell.estate_sell_status_name,
                estate_price=sell.estate_price,
                estate_area=sell.estate_area
            )
            db.session.add(new_sell)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи объектов продажи: {len(mysql_sells)}")

        db.session.commit() # Commit the new data
        print("[MIGRATE] ✔️ Данные недвижимости успешно сохранены.")

    except Exception as e:
        print(f"[MIGRATE] ❌ ОШИБКА во время миграции данных недвижимости: {e}")
        db.session.rollback() # Rollback on error
        raise e
    finally:
        mysql_session.close()
        print("[MIGRATE] 🔌 Соединение с MySQL закрыто.")


def load_all_initial_data(is_initial_setup=False):
    """
    Наполняет локальную БД данными из MySQL и Excel.
    Вызывается только при ПЕРВОНАЧАЛЬНОМ запуске, когда БД пуста.

    is_initial_setup: True, если это первый запуск приложения и БД создается.
    """
    print("\n[INITIAL LOAD] 🚀 НАЧАЛО ПРОЦЕССА ПЕРВОНАЧАЛЬНОЙ ЗАГРУЗКИ ДАННЫХ...")

    if is_initial_setup:
        # Create all tables if it's the very first setup
        print("[INITIAL LOAD] 🛠️ Создание всех таблиц базы данных...")
        db.create_all()
        print("[INITIAL LOAD] ✔️ Таблицы созданы.")

    try:
        # 1. Мигрируем данные по недвижимости из MySQL
        # _migrate_mysql_estate_data_to_sqlite уже очищает EstateHouse и EstateSell
        _migrate_mysql_estate_data_to_sqlite()

        # 2. Загружаем скидки из Excel (только если их нет или нужно перезаписать)
        # Очищаем существующие версии скидок для чистой начальной загрузки
        print("[INITIAL LOAD] 🧹 Очистка существующих версий скидок для начальной загрузки...")
        db.session.query(Discount).delete()
        db.session.query(DiscountVersion).delete()
        db.session.commit()
        print("[INITIAL LOAD] ✔️ Версии скидок очищены.")


        if os.path.exists(DISCOUNTS_EXCEL_PATH):
            print(f"[INITIAL LOAD] 📥 Загрузка скидок из файла: {DISCOUNTS_EXCEL_PATH}")
            initial_version = DiscountVersion(
                version_number=1,
                comment="Начальная загрузка из Excel",
                is_active=True
            )
            db.session.add(initial_version)
            db.session.flush() # Get ID for initial_version

            process_discounts_from_excel(DISCOUNTS_EXCEL_PATH, initial_version.id)
            print("[INITIAL LOAD] ✔️ Скидки из Excel успешно подготовлены в 'Версию 1'.")
        else:
            print(f"[INITIAL LOAD] ⚠️  ВНИМАНИЕ: Файл со скидками не найден ({DISCOUNTS_EXCEL_PATH}). Пропускаем шаг.")

        db.session.commit() # Final commit for the initial load process
        print("[INITIAL LOAD] ✅ ПРОЦЕСС ПЕРВОНАЧАЛЬНОЙ ЗАГРУЗКИ ЗАВЕРШЕН.\n")

    except Exception as e:
        print(f"[INITIAL LOAD] ❌ Ошибка при полной загрузке данных: {e}")
        db.session.rollback()
        raise e


# New function for the refresh button
def refresh_estate_data_from_mysql():
    """
    Обновляет только данные по недвижимости (дома, квартиры) из MySQL.
    Используется для кнопки "Обновить данные".
    """
    print("\n[REFRESH DATA] 🔄 НАЧАЛО ПРОЦЕССА ОБНОВЛЕНИЯ ДАННЫХ НЕДВИЖИМОСТИ ИЗ MySQL...")
    try:
        _migrate_mysql_estate_data_to_sqlite()
        print("[REFRESH DATA] ✅ ДАННЫЕ НЕДВИЖИМОСТИ УСПЕШНО ОБНОВЛЕНЫ ИЗ MySQL.\n")
        return True
    except Exception as e:
        print(f"[REFRESH DATA] ❌ ОШИБКА ПРИ ОБНОВЛЕНИИ ДАННЫХ НЕДВИЖИМОСТИ: {e}")
        return False