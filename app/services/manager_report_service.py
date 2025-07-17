# app/services/manager_report_service.py
from sqlalchemy import or_
import pandas as pd
import re
from datetime import datetime, date
from collections import defaultdict
from sqlalchemy import func, extract
import io

from app.core.extensions import db

# Обновленные импорты
from app.models import auth_models
from app.models import planning_models
from app.models.estate_models import EstateDeal, EstateSell, EstateHouse
from app.models.finance_models import FinanceOperation


def process_manager_plans_from_excel(file_path: str):
    """
    Обрабатывает Excel-файл с персональными планами менеджеров.
    """
    df = pd.read_excel(file_path)
    plans_to_save = defaultdict(lambda: defaultdict(float))
    header_pattern = re.compile(r"(контрактация|поступления) (\d{2}\.\d{2}\.\d{4})", re.IGNORECASE)

    # Используем auth_models.SalesManager
    managers_map = {m.full_name: m.id for m in auth_models.SalesManager.query.all()}

    for index, row in df.iterrows():
        manager_name = row.iloc[0]
        if manager_name not in managers_map:
            print(f"[MANAGER PLANS] ⚠️ ВНИМАНИЕ: Менеджер '{manager_name}' не найден в базе. Строка пропущена.")
            continue
        manager_id = managers_map[manager_name]

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

    updated_count, created_count = 0, 0
    for (manager_id, year, month), values in plans_to_save.items():
        # Используем planning_models.ManagerSalesPlan
        plan_entry = planning_models.ManagerSalesPlan.query.filter_by(manager_id=manager_id, year=year,
                                                                      month=month).first()
        if not plan_entry:
            plan_entry = planning_models.ManagerSalesPlan(manager_id=manager_id, year=year, month=month)
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
    manager = auth_models.SalesManager.query.get(manager_id)
    if not manager:
        return None

    plans_query = planning_models.ManagerSalesPlan.query.filter_by(manager_id=manager_id, year=year).all()
    plan_data = {p.month: p for p in plans_query}

    # Этот запрос для "Контрактации" остается без изменений
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

    # --- НАЧАЛО ОТЛАДОЧНОГО БЛОКА ---

    print("\n" + "=" * 50)
    print(f"🕵️ [ОТЛАДКА] Начинаем прямой поиск поступлений для Менеджера ID: {manager_id} за {year} год.")

    # Этап 1: Ищем ВСЕ операции в таблице финансов для этого ID менеджера
    base_query = db.session.query(FinanceOperation).filter(FinanceOperation.manager_id == manager_id)
    print(f"✔️ [Этап 1] Найдено ВСЕГО финансовых операций для manager_id={manager_id}: {base_query.count()}")

    # Этап 2: Добавляем фильтр по году
    query_after_year_filter = base_query.filter(extract('year', FinanceOperation.date_added) == year)
    print(f"✔️ [Этап 2] Осталось операций после фильтра по {year} году: {query_after_year_filter.count()}")

    # Этап 3: Добавляем фильтр по статусу "Проведено"
    query_after_status_filter = query_after_year_filter.filter(FinanceOperation.status_name == "Проведено")
    print(f"✔️ [Этап 3] Осталось операций после фильтра по статусу 'Проведено': {query_after_status_filter.count()}")

    # Этап 4: Проверим, какие типы платежей есть у найденных операций
    if query_after_status_filter.count() > 0:
        found_payment_types = [res[0] for res in
                               query_after_status_filter.with_entities(FinanceOperation.payment_type).distinct().all()]
        print(f"ℹ️ [ИНФО] У этих операций найдены следующие типы платежей: {found_payment_types}")

    # Этап 5: Добавляем финальный фильтр, исключающий возвраты
    final_query_before_grouping = query_after_status_filter.filter(
        or_(
            FinanceOperation.payment_type != "Возврат поступлений при отмене сделки",
            FinanceOperation.payment_type.is_(None)
        )
    )
    print(
        f"✔️ [Этап 4] Осталось операций после исключения возвратов и добавления NULL: {final_query_before_grouping.count()}")

    # Финальный запрос для получения данных
    fact_income_query = final_query_before_grouping.with_entities(
        extract('month', FinanceOperation.date_added).label('month'),
        func.sum(FinanceOperation.summa).label('fact_income')
    ).group_by('month').all()

    print(f"✅ [РЕЗУЛЬТАТ] Итоговый запрос вернул {len(fact_income_query)} сгруппированных по месяцам записей.")
    print("=" * 50 + "\n")

    # --- КОНЕЦ ОТЛАДОЧНОГО БЛОКА ---

    fact_income_data = {row.month: row.fact_income or 0 for row in fact_income_query}

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
    managers = auth_models.SalesManager.query.order_by(auth_models.SalesManager.full_name).all()
    manager_names = [manager.full_name for manager in managers]

    current_year = date.today().year
    headers = ['ФИО']
    for month in range(1, 13):
        date_str = f"01.{month:02d}.{current_year}"
        headers.append(f"Контрактация {date_str}")
        headers.append(f"Поступления {date_str}")

    data = [{'ФИО': name, **{header: 0 for header in headers[1:]}} for name in manager_names]

    df = pd.DataFrame(data, columns=headers)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Шаблон планов')
        worksheet = writer.sheets['Шаблон планов']
        worksheet.column_dimensions['A'].width = 35
        for i in range(1, len(headers)):
            col_letter = chr(ord('B') + i - 1)
            worksheet.column_dimensions[col_letter].width = 25
    output.seek(0)
    return output


def get_manager_kpis(manager_id: int, year: int):
    """
    Рассчитывает расширенные KPI для одного менеджера.
    """
    sold_statuses = ["Сделка в работе", "Сделка проведена"]

    best_complex_query = db.session.query(
        EstateHouse.complex_name, func.count(EstateDeal.id).label('deal_count')
    ).join(EstateSell, EstateHouse.sells).join(EstateDeal, EstateSell.deals) \
        .filter(
        EstateDeal.deal_manager_id == manager_id,
        EstateDeal.deal_status_name.in_(sold_statuses)
    ).group_by(EstateHouse.complex_name).order_by(func.count(EstateDeal.id).desc()).first()

    units_by_type_query = db.session.query(
        EstateSell.estate_sell_category, func.count(EstateDeal.id).label('unit_count')
    ).join(EstateDeal, EstateSell.deals).filter(
        EstateDeal.deal_manager_id == manager_id,
        EstateDeal.deal_status_name.in_(sold_statuses)
    ).group_by(EstateSell.estate_sell_category).all()

    effective_date = func.coalesce(EstateDeal.agreement_date, EstateDeal.preliminary_date)

    best_year_volume_query = db.session.query(
        extract('year', effective_date).label('deal_year'),
        func.sum(EstateDeal.deal_sum).label('total_volume')
    ).filter(
        EstateDeal.deal_manager_id == manager_id,
        effective_date.isnot(None),
        EstateDeal.deal_status_name.in_(sold_statuses)
    ).group_by('deal_year').order_by(func.sum(EstateDeal.deal_sum).desc()).first()

    best_month_volume_query = db.session.query(
        extract('year', effective_date).label('deal_year'),
        extract('month', effective_date).label('deal_month'),
        func.sum(EstateDeal.deal_sum).label('total_volume')
    ).filter(
        EstateDeal.deal_manager_id == manager_id,
        effective_date.isnot(None),
        EstateDeal.deal_status_name.in_(sold_statuses)
    ).group_by('deal_year', 'deal_month').order_by(func.sum(EstateDeal.deal_sum).desc()).first()

    best_month_in_year_volume_query = db.session.query(
        extract('month', effective_date).label('deal_month'),
        func.sum(EstateDeal.deal_sum).label('total_volume')
    ).filter(
        EstateDeal.deal_manager_id == manager_id,
        extract('year', effective_date) == year,
        EstateDeal.deal_status_name.in_(sold_statuses)
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
    Возвращает рейтинг ЖК по количеству и объему сделок для конкретного менеджера.
    """
    sold_statuses = ["Сделка в работе", "Сделка проведена"]
    ranking = db.session.query(
        EstateHouse.complex_name,
        func.sum(EstateDeal.deal_sum).label('total_volume'),
        func.count(EstateDeal.id).label('deal_count')
    ).join(EstateSell, EstateHouse.sells) \
        .join(EstateDeal, EstateSell.deals) \
        .filter(
        EstateDeal.deal_manager_id == manager_id,
        EstateDeal.deal_status_name.in_(sold_statuses)
    ) \
        .group_by(EstateHouse.complex_name) \
        .order_by(func.count(EstateDeal.id).desc()) \
        .all()
    return [{"name": r.complex_name, "total_volume": r.total_volume, "deal_count": r.deal_count} for r in ranking]


def get_complex_hall_of_fame(complex_name: str, start_date_str: str = None, end_date_str: str = None):
    """
    Возвращает рейтинг менеджеров по количеству и объему сделок для ЖК.
    """
    sold_statuses = ["Сделка в работе", "Сделка проведена"]
    query = db.session.query(
        auth_models.SalesManager.full_name,
        func.count(EstateDeal.id).label('deal_count'),
        func.sum(EstateDeal.deal_sum).label('total_volume'),
        func.sum(EstateSell.estate_area).label('total_area')
    ).join(EstateDeal, auth_models.SalesManager.id == EstateDeal.deal_manager_id) \
        .join(EstateSell, EstateDeal.estate_sell_id == EstateSell.id) \
        .join(EstateHouse, EstateSell.house_id == EstateHouse.id) \
        .filter(
        EstateHouse.complex_name == complex_name,
        EstateDeal.deal_status_name.in_(sold_statuses)
    )

    if start_date_str:
        start_date = date.fromisoformat(start_date_str)
        query = query.filter(func.coalesce(EstateDeal.agreement_date, EstateDeal.preliminary_date) >= start_date)
    if end_date_str:
        end_date = date.fromisoformat(end_date_str)
        query = query.filter(func.coalesce(EstateDeal.agreement_date, EstateDeal.preliminary_date) <= end_date)

    ranking = query.group_by(auth_models.SalesManager.id).order_by(func.count(EstateDeal.id).desc()).all()
    return ranking