# app/services/manager_report_service.py

import pandas as pd
import re
from datetime import datetime
from collections import defaultdict
from sqlalchemy import func, extract
import io
from datetime import date
from app.core.extensions import db
from app.models.user_models import SalesManager
from app.models.discount_models import ManagerSalesPlan
from app.models.estate_models import EstateDeal, EstateSell
from app.models.finance_models import FinanceOperation
from app.models.estate_models import EstateHouse

def process_manager_plans_from_excel(file_path: str):
    """
    Обрабатывает Excel-файл с персональными планами менеджеров.
    Структура файла: ФИО, [Контрактация ДД.ММ.ГГГГ], [Поступления ДД.ММ.ГГГГ], ...
    """
    df = pd.read_excel(file_path)
    # Словарь для накопления данных перед записью в БД
    # Формат: {(manager_id, year, month): {'plan_volume': X, 'plan_income': Y}}
    plans_to_save = defaultdict(lambda: defaultdict(float))

    # Паттерн для извлечения даты и типа из заголовка
    header_pattern = re.compile(r"(контрактация|поступления) (\d{2}\.\d{2}\.\d{4})", re.IGNORECASE)

    # Получаем словарь всех менеджеров для быстрого поиска ID
    managers_map = {m.full_name: m.id for m in SalesManager.query.all()}

    # Проходим по каждой строке (каждому менеджеру)
    for index, row in df.iterrows():
        manager_name = row.iloc[0]
        if manager_name not in managers_map:
            print(f"[MANAGER PLANS] ⚠️ ВНИМАНИЕ: Менеджер '{manager_name}' не найден в базе. Строка пропущена.")
            continue

        manager_id = managers_map[manager_name]

        # Проходим по каждой колонке с планом
        for col_name, value in row.iloc[1:].items():
            if pd.isna(value) or value == 0:
                continue

            match = header_pattern.search(str(col_name))
            if not match:
                continue

            plan_type_str, date_str = match.groups()
            plan_date = datetime.strptime(date_str, '%d.%m.%Y')
            year, month = plan_date.year, plan_date.month

            if 'контрактация' in plan_type_str.lower():
                plans_to_save[(manager_id, year, month)]['plan_volume'] += float(value)
            elif 'поступления' in plan_type_str.lower():
                plans_to_save[(manager_id, year, month)]['plan_income'] += float(value)

    # Сохраняем агрегированные данные в базу
    updated_count = 0
    created_count = 0
    for (manager_id, year, month), values in plans_to_save.items():
        plan_entry = ManagerSalesPlan.query.filter_by(manager_id=manager_id, year=year, month=month).first()
        if not plan_entry:
            plan_entry = ManagerSalesPlan(manager_id=manager_id, year=year, month=month)
            db.session.add(plan_entry)
            created_count += 1

        plan_entry.plan_volume = values.get('plan_volume', 0.0)
        plan_entry.plan_income = values.get('plan_income', 0.0)
        updated_count += 1

    db.session.commit()
    return f"Успешно обработано планов: создано {created_count}, обновлено {updated_count}."


def get_manager_performance_details(manager_id: int, year: int):
    """
    Собирает детальную информацию по выполнению плана для одного менеджера за год.
    """
    manager = SalesManager.query.get(manager_id)
    if not manager:
        return None

    # 1. Получаем все планы менеджера за год
    plans_query = ManagerSalesPlan.query.filter_by(manager_id=manager_id, year=year).all()
    plan_data = {p.month: p for p in plans_query}

    # 2. Получаем фактическую контрактацию (объем сделок)
    effective_date = func.coalesce(EstateDeal.agreement_date, EstateDeal.preliminary_date)
    fact_volume_query = db.session.query(
        extract('month', effective_date).label('month'),
        func.sum(EstateDeal.deal_sum).label('fact_volume')
    ).filter(
        EstateDeal.deal_manager_id == manager_id,
        extract('year', effective_date) == year,
        EstateDeal.deal_status_name.in_(["Сделка в работе", "Сделка проведена"])
    ).group_by('month').all()
    fact_volume_data = {row.month: row.fact_volume or 0 for row in fact_volume_query}

    # 3. Получаем фактические поступления
    fact_income_query = db.session.query(
        extract('month', FinanceOperation.date_added).label('month'),
        func.sum(FinanceOperation.summa).label('fact_income')
    ).join(EstateSell, FinanceOperation.estate_sell_id == EstateSell.id) \
        .join(EstateDeal, EstateSell.id == EstateDeal.estate_sell_id) \
        .filter(
        EstateDeal.deal_manager_id == manager_id,
        extract('year', FinanceOperation.date_added) == year,
        FinanceOperation.status_name == "Проведено"
    ).group_by('month').all()
    fact_income_data = {row.month: row.fact_income or 0 for row in fact_income_query}

    # 4. Собираем итоговый отчет
    report = []
    for month_num in range(1, 13):
        plan = plan_data.get(month_num)
        fact_volume = fact_volume_data.get(month_num, 0)
        fact_income = fact_income_data.get(month_num, 0)

        report.append({
            'month': month_num,
            'plan_volume': plan.plan_volume if plan else 0,
            'fact_volume': fact_volume,
            'volume_percent': (fact_volume / plan.plan_volume * 100) if (plan and plan.plan_volume > 0) else 0,
            'plan_income': plan.plan_income if plan else 0,
            'fact_income': fact_income,
            'income_percent': (fact_income / plan.plan_income * 100) if (plan and plan.plan_income > 0) else 0,
        })

    return {'manager_name': manager.full_name, 'performance': report}

def generate_manager_plan_template_excel():
    """
    Генерирует Excel-файл с ФИО всех менеджеров и столбцами планов на текущий год.
    """
    # 1. Получаем список всех менеджеров
    managers = SalesManager.query.order_by(SalesManager.full_name).all()
    manager_names = [manager.full_name for manager in managers]

    # 2. Формируем заголовки для каждого месяца текущего года
    current_year = date.today().year
    headers = ['ФИО']
    for month in range(1, 13):
        # Формат даты в заголовке должен точно соответствовать тому, что ожидает парсер
        date_str = f"01.{month:02d}.{current_year}"
        headers.append(f"Контрактация {date_str}")
        headers.append(f"Поступления {date_str}")

    # 3. Создаем данные для DataFrame
    data = []
    for name in manager_names:
        row = {'ФИО': name}
        # Заполняем все плановые ячейки нулями по умолчанию
        for header in headers[1:]:
            row[header] = 0
        data.append(row)

    # 4. Создаем Excel-файл в памяти
    df = pd.DataFrame(data, columns=headers)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Шаблон планов')
        # Можно добавить автоширину колонок для удобства
        worksheet = writer.sheets['Шаблон планов']
        worksheet.column_dimensions['A'].width = 35 # Делаем столбец с ФИО пошире
        for col_idx in range(1, len(headers)):
            col_letter = chr(ord('B') + col_idx - 1)
            worksheet.column_dimensions[col_letter].width = 25


    output.seek(0)
    return output


def get_manager_kpis(manager_id: int, year: int):
    """
    Рассчитывает расширенные KPI для одного менеджера.
    """
    # 1. Лучший продаваемый ЖК (название и количество сделок)
    best_complex_query = db.session.query(
        EstateHouse.complex_name,
        func.count(EstateDeal.id).label('deal_count')
    ).join(EstateSell, EstateHouse.sells).join(EstateDeal, EstateSell.deals) \
        .filter(EstateDeal.deal_manager_id == manager_id) \
        .group_by(EstateHouse.complex_name).order_by(func.count(EstateDeal.id).desc()).first()

    # 2. Количество проданных юнитов по типам
    units_by_type_query = db.session.query(
        EstateSell.estate_sell_category, func.count(EstateDeal.id).label('unit_count')
    ).join(EstateDeal, EstateSell.deals).filter(EstateDeal.deal_manager_id == manager_id) \
        .group_by(EstateSell.estate_sell_category).all()

    effective_date = func.coalesce(EstateDeal.agreement_date, EstateDeal.preliminary_date)

    # 3. Лучший ГОД по контрактации (за все время)
    best_year_volume_query = db.session.query(
        extract('year', effective_date).label('deal_year'),
        func.sum(EstateDeal.deal_sum).label('total_volume')
    ).filter(EstateDeal.deal_manager_id == manager_id, effective_date.isnot(None)) \
        .group_by('deal_year').order_by(func.sum(EstateDeal.deal_sum).desc()).first()

    # 4. Лучший МЕСЯЦ по контрактации (за все время)
    best_month_volume_query = db.session.query(
        extract('year', effective_date).label('deal_year'),
        extract('month', effective_date).label('deal_month'),
        func.sum(EstateDeal.deal_sum).label('total_volume')
    ).filter(EstateDeal.deal_manager_id == manager_id, effective_date.isnot(None)) \
        .group_by('deal_year', 'deal_month').order_by(func.sum(EstateDeal.deal_sum).desc()).first()

    # 5. Лучший месяц по контрактации в ВЫБРАННОМ году
    best_month_in_year_volume_query = db.session.query(
        extract('month', effective_date).label('deal_month'),
        func.sum(EstateDeal.deal_sum).label('total_volume')
    ).filter(
        EstateDeal.deal_manager_id == manager_id,
        extract('year', effective_date) == year
    ).group_by('deal_month').order_by(func.sum(EstateDeal.deal_sum).desc()).first()

    kpis = {
        'best_complex': {
            'name': best_complex_query.complex_name if best_complex_query else None,
            'count': best_complex_query.deal_count if best_complex_query else 0
        },
        'units_by_type': {row.estate_sell_category: row.unit_count for row in units_by_type_query},
        'best_month_in_year': {
            'volume': {
                'month': int(best_month_in_year_volume_query.deal_month) if best_month_in_year_volume_query else 0,
                'total': best_month_in_year_volume_query.total_volume if best_month_in_year_volume_query else 0
            }
        },
        'all_time_records': {
            'best_year_volume': {
                'year': int(best_year_volume_query.deal_year) if best_year_volume_query else 0,
                'total': best_year_volume_query.total_volume if best_year_volume_query else 0
            },
            'best_month_volume': {
                'year': int(best_month_volume_query.deal_year) if best_month_volume_query else 0,
                'month': int(best_month_volume_query.deal_month) if best_month_volume_query else 0,
                'total': best_month_volume_query.total_volume if best_month_volume_query else 0
            }
        }
    }

    return kpis


def get_manager_complex_ranking(manager_id: int):
    """
    Возвращает рейтинг ЖК по сумме сделок для конкретного менеджера.
    """
    ranking = db.session.query(
        EstateHouse.complex_name,
        func.sum(EstateDeal.deal_sum).label('total_volume'),
        func.count(EstateDeal.id).label('deal_count')
    ).join(EstateSell, EstateHouse.sells)\
     .join(EstateDeal, EstateSell.deals)\
     .filter(EstateDeal.deal_manager_id == manager_id)\
     .group_by(EstateHouse.complex_name)\
     .order_by(func.sum(EstateDeal.deal_sum).desc())\
     .all()

    return [{"name": r.complex_name, "total_volume": r.total_volume, "deal_count": r.deal_count} for r in ranking]