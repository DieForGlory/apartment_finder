import os
from sqlalchemy import create_engine, Table, Column, Integer, String, MetaData
from sqlalchemy.orm import sessionmaker
from flask import current_app

from ..core.extensions import db
from .discount_service import process_discounts_from_excel

# Обновленные импорты моделей
from ..models import auth_models
from ..models import planning_models
from ..models.estate_models import EstateHouse, EstateSell, EstateDeal
from ..models.finance_models import FinanceOperation
from ..models.funnel_models import EstateBuy, EstateBuysStatusLog

CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
DISCOUNTS_EXCEL_PATH = os.path.join(PROJECT_ROOT, 'data_sources', 'discounts_template.xlsx')


def _migrate_mysql_estate_data_to_sqlite():
    """
    Подключается к MySQL, извлекает данные и перезаписывает их в соответствующие базы данных SQLite.
    """
    print("[MIGRATE] 🔄 Начало миграции данных из MySQL...")

    mysql_uri = current_app.config['SOURCE_MYSQL_URI']
    mysql_engine = create_engine(mysql_uri)
    MySQLSession = sessionmaker(bind=mysql_engine)
    mysql_session = MySQLSession()

    try:
        print("[MIGRATE] 🧹 Очистка существующих данных...")
        # Очистка таблиц в основной БД
        db.session.query(EstateDeal).delete()
        db.session.query(EstateSell).delete()
        db.session.query(EstateHouse).delete()
        db.session.query(FinanceOperation).delete()
        db.session.query(EstateBuysStatusLog).delete()
        db.session.query(EstateBuy).delete()

        # Очистка таблиц в auth_db и planning_db
        db.session.query(auth_models.SalesManager).delete()
        db.session.query(planning_models.ManagerSalesPlan).delete()

        db.session.commit()
        print("[MIGRATE] ✔️ Данные очищены.")

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

        print("[MIGRATE] funnel: Заявки из 'estate_buys'...")
        mysql_buys = mysql_session.query(EstateBuy).all()
        for buy in mysql_buys:
            new_buy = EstateBuy(
                id=buy.id,
                date_added=buy.date_added,
                created_at=buy.created_at,
                status_name=buy.status_name,
                custom_status_name=buy.custom_status_name
            )
            db.session.add(new_buy)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи заявок: {len(mysql_buys)}")

        print("[MIGRATE] funnel: Лог статусов из 'estate_buys_statuses_log'...")
        mysql_logs = mysql_session.query(EstateBuysStatusLog).all()
        for log in mysql_logs:
            new_log = EstateBuysStatusLog(
                id=log.id,
                log_date=log.log_date,
                estate_buy_id=log.estate_buy_id,
                status_to_name=log.status_to_name,
                status_custom_to_name=log.status_custom_to_name
            )
            db.session.add(new_log)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи логов: {len(mysql_logs)}")

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
                estate_sell_category=ESTATE_SELL_CATEGORY_MAPPING.get(sell.estate_sell_category,
                                                                      sell.estate_sell_category),
                estate_floor=sell.estate_floor,
                estate_rooms=sell.estate_rooms,
                estate_price_m2=sell.estate_price_m2,
                estate_sell_status_name=sell.estate_sell_status_name,
                estate_price=sell.estate_price,
                estate_area=sell.estate_area
            )
            db.session.add(new_sell)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи объектов продажи: {len(mysql_sells)}")

        # 3. Миграция менеджеров
        print("[MIGRATE] 🧑‍💼 Загрузка данных менеджеров из таблицы 'users'...")
        meta = MetaData()
        mysql_users_table = Table('users', meta, Column('id', Integer, primary_key=True), Column('users_name', String))
        mysql_managers = mysql_session.query(mysql_users_table).all()
        processed_names = set()
        added_count = 0
        for manager in mysql_managers:
            cleaned_name = (manager.users_name or "").strip()
            if not cleaned_name or cleaned_name in processed_names:
                continue
            processed_names.add(cleaned_name)
            new_manager = auth_models.SalesManager(id=manager.id, full_name=cleaned_name)
            db.session.add(new_manager)
            added_count += 1
        print(
            f"[MIGRATE] ✔️ Найдено менеджеров в источнике: {len(mysql_managers)}. Добавлено уникальных: {added_count}")

        # 4. Миграция таблицы estate_deals
        print("[MIGRATE] 🤝 Загрузка данных из таблицы 'estate_deals'...")
        mysql_deals = mysql_session.query(EstateDeal).all()
        for deal in mysql_deals:
            new_deal = EstateDeal(
                id=deal.id,
                estate_sell_id=deal.estate_sell_id,
                deal_status_name=deal.deal_status_name,
                deal_manager_id=deal.deal_manager_id,
                agreement_date=deal.agreement_date,
                preliminary_date=deal.preliminary_date,
                deal_sum=deal.deal_sum
            )
            db.session.add(new_deal)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи сделок: {len(mysql_deals)}")

        # 5. Миграция таблицы finances
        print("[MIGRATE] 💰 Загрузка данных из таблицы 'finances'...")
        mysql_finances = mysql_session.query(FinanceOperation).all()
        for fin_op in mysql_finances:
            new_fin_op = FinanceOperation(
                id=fin_op.id,
                estate_sell_id=fin_op.estate_sell_id,
                summa=fin_op.summa,
                status_name=fin_op.status_name,
                date_added=fin_op.date_added
            )
            db.session.add(new_fin_op)
        print(f"[MIGRATE] ✔️ Найдено и подготовлено к записи фин. операций: {len(mysql_finances)}")

        db.session.commit()
        print("[MIGRATE] ✔️ Все данные успешно сохранены в SQLite.")

    except Exception as e:
        print(f"[MIGRATE] ❌ ОШИБКА во время миграции: {e}")
        db.session.rollback()
        raise e
    finally:
        mysql_session.close()
        print("[MIGRATE] 🔌 Соединение с MySQL закрыто.")


def load_all_initial_data(is_initial_setup=False):
    """
    Наполняет ВСЕ базы данных. Вызывается только при ПЕРВОНАЧАЛЬНОМ запуске.
    """
    print("\n[INITIAL LOAD] 🚀 НАЧАЛО ПРОЦЕССА ПЕРВОНАЧАЛЬНОЙ ЗАГРУЗКИ ДАННЫХ...")

    if is_initial_setup:
        print("[INITIAL LOAD] 🛠️ Создание таблиц во всех базах...")
        db.create_all()
        print("[INITIAL LOAD] ✔️ Таблицы созданы.")

    try:
        _migrate_mysql_estate_data_to_sqlite()

        print("[INITIAL LOAD] 🧹 Очистка существующих версий скидок...")
        db.session.query(planning_models.Discount).delete(synchronize_session=False)
        db.session.query(planning_models.DiscountVersion).delete(synchronize_session=False)
        db.session.commit()
        print("[INITIAL LOAD] ✔️ Версии скидок очищены.")

        if os.path.exists(DISCOUNTS_EXCEL_PATH):
            print(f"[INITIAL LOAD] 📥 Загрузка скидок из файла: {DISCOUNTS_EXCEL_PATH}")
            initial_version = planning_models.DiscountVersion(
                version_number=1,
                comment="Начальная загрузка из Excel",
                is_active=True
            )
            db.session.add(initial_version)
            db.session.flush()
            process_discounts_from_excel(DISCOUNTS_EXCEL_PATH, initial_version.id)
            print("[INITIAL LOAD] ✔️ Скидки из Excel успешно подготовлены в 'Версию 1'.")
        else:
            print(f"[INITIAL LOAD] ⚠️  ВНИМАНИЕ: Файл со скидками не найден ({DISCOUNTS_EXCEL_PATH}).")

        db.session.commit()
        print("[INITIAL LOAD] ✅ ПРОЦЕСС ПЕРВОНАЧАЛЬНОЙ ЗАГРУЗКИ ЗАВЕРШЕН.\n")
    except Exception as e:
        print(f"[INITIAL LOAD] ❌ Ошибка при полной загрузке данных: {e}")
        db.session.rollback()
        raise e


def refresh_estate_data_from_mysql():
    """
    Обновляет данные из MySQL. НЕ ТРОГАЕТ СКИДКИ.
    """
    print("\n[REFRESH DATA] 🔄 НАЧАЛО ПРОЦЕССА ОБНОВЛЕНИЯ ДАННЫХ ИЗ MySQL...")
    try:
        _migrate_mysql_estate_data_to_sqlite()
        print("[REFRESH DATA] ✅ ДАННЫЕ УСПЕШНО ОБНОВЛЕНЫ ИЗ MySQL.\n")
        return True
    except Exception as e:
        print(f"[REFRESH DATA] ❌ ОШИБКА ПРИ ОБНОВЛЕНИИ ДАННЫХ: {e}")
        return False