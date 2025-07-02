# app/services/report_service.py
import pandas as pd
import numpy as np
from datetime import date
from sqlalchemy import func, extract, case
from app.core.extensions import db
from app.models.discount_models import SalesPlan, PropertyType
import io
from sqlalchemy.dialects import sqlite
from .data_service import get_all_complex_names
from ..models.estate_models import EstateDeal, EstateHouse, EstateSell
from ..models.finance_models import FinanceOperation


def get_fact_income_data(year: int, month: int, property_type: str):
    """Собирает ФАКТИЧЕСКИЕ поступления (статус 'Проведено')."""
    results = db.session.query(
        EstateHouse.complex_name, func.sum(FinanceOperation.summa).label('fact_income')
    ).join(EstateSell, FinanceOperation.estate_sell_id == EstateSell.id)\
     .join(EstateHouse, EstateSell.house_id == EstateHouse.id)\
     .filter(
        FinanceOperation.status_name == "Проведено",
        extract('year', FinanceOperation.date_added) == year,
        extract('month', FinanceOperation.date_added) == month,
        EstateSell.estate_sell_category == property_type
    ).group_by(EstateHouse.complex_name).all()
    return {row.complex_name: (row.fact_income or 0) for row in results}

def get_expected_income_data(year: int, month: int, property_type: str):
    """Собирает ОЖИДАЕМЫЕ поступления (статус НЕ 'Проведено')."""
    results = db.session.query(
        EstateHouse.complex_name, func.sum(FinanceOperation.summa).label('expected_income')
    ).join(EstateSell, FinanceOperation.estate_sell_id == EstateSell.id)\
     .join(EstateHouse, EstateSell.house_id == EstateHouse.id)\
     .filter(
        FinanceOperation.status_name == "К оплате",
        extract('year', FinanceOperation.date_added) == year,
        extract('month', FinanceOperation.date_added) == month,
        EstateSell.estate_sell_category == property_type
    ).group_by(EstateHouse.complex_name).all()
    return {row.complex_name: (row.expected_income or 0) for row in results}

def get_plan_income_data(year: int, month: int, property_type: str):
    """Получает плановые данные по поступлениям."""
    results = SalesPlan.query.filter_by(year=year, month=month, property_type=property_type).all()
    return {row.complex_name: row.plan_income for row in results}

def get_fact_data(year: int, month: int, property_type: str):
    """Собирает фактические данные о продажах из БД."""

    effective_date = func.coalesce(EstateDeal.agreement_date, EstateDeal.preliminary_date)

    # Запрос теперь использует связи между таблицами
    query = db.session.query(
        EstateHouse.complex_name,
        func.count(EstateDeal.id).label('fact_units')
    ).join(
        EstateSell, EstateDeal.estate_sell_id == EstateSell.id
    ).join(
        EstateHouse, EstateSell.house_id == EstateHouse.id
    ).filter(
        EstateDeal.deal_status_name.in_(["Сделка в работе", "Сделка проведена"]),
        extract('year', effective_date) == year,
        extract('month', effective_date) == month,
        EstateSell.estate_sell_category == property_type
    ).group_by(EstateHouse.complex_name)

    results = query.all()

    return {row.complex_name: row.fact_units for row in results}


def get_plan_data(year: int, month: int, property_type: str):
    """Получает плановые данные из нашей таблицы SalesPlan."""

    results = SalesPlan.query.filter_by(
        year=year,
        month=month,
        property_type=property_type
    ).all()

    return {row.complex_name: row.plan_units for row in results}


def generate_plan_fact_report(year: int, month: int, property_type: str):
    """Основная функция для генерации отчета, возвращающая детализацию и итоги."""
    # ... (код получения данных plan_units_data, fact_units_data и т.д. остается без изменений) ...
    plan_units_data = get_plan_data(year, month, property_type)
    fact_units_data = get_fact_data(year, month, property_type)
    plan_volume_data = get_plan_volume_data(year, month, property_type)
    fact_volume_data = get_fact_volume_data(year, month, property_type)
    plan_income_data = get_plan_income_data(year, month, property_type)
    fact_income_data = get_fact_income_data(year, month, property_type)
    expected_income_data = get_expected_income_data(year, month, property_type)

    all_complexes = sorted(
        list(set(plan_units_data.keys()) | set(fact_units_data.keys()) | set(plan_income_data.keys())))

    report_data = []
    # Инициализируем словарь для итогов
    totals = {
        'plan_units': 0, 'fact_units': 0, 'plan_volume': 0, 'fact_volume': 0,
        'plan_income': 0, 'fact_income': 0, 'expected_income': 0
    }

    # ... (код для расчета workdays без изменений) ...
    today = date.today()
    workdays_in_month = np.busday_count(f'{year}-{month:02d}-01',
                                        f'{year}-{month + 1:02d}-01' if month < 12 else f'{year + 1}-01-01')
    passed_workdays = np.busday_count(f'{year}-{month:02d}-01',
                                      today) if today.month == month and today.year == year else workdays_in_month
    passed_workdays = max(1, passed_workdays)

    for complex_name in all_complexes:
        # Штуки
        plan_units = plan_units_data.get(complex_name, 0)
        fact_units = fact_units_data.get(complex_name, 0)
        # ИЗМЕНЕНИЕ: Считаем % выполнения плана, а не отклонение
        percent_fact_units = (fact_units / plan_units) * 100 if plan_units > 0 else 0
        forecast_units = ((
                                      fact_units / passed_workdays) * workdays_in_month / plan_units) * 100 if plan_units > 0 else 0

        # Контрактация
        plan_volume = plan_volume_data.get(complex_name, 0)
        fact_volume = fact_volume_data.get(complex_name, 0)
        percent_fact_volume = (fact_volume / plan_volume) * 100 if plan_volume > 0 else 0
        forecast_volume = ((
                                       fact_volume / passed_workdays) * workdays_in_month / plan_volume) * 100 if plan_volume > 0 else 0

        # Поступления
        plan_income = plan_income_data.get(complex_name, 0)
        fact_income = fact_income_data.get(complex_name, 0)
        expected_income = expected_income_data.get(complex_name, 0)
        percent_fact_income = (fact_income / plan_income) * 100 if plan_income > 0 else 0

        # Суммируем в итоги
        totals['plan_units'] += plan_units
        totals['fact_units'] += fact_units
        totals['plan_volume'] += plan_volume
        totals['fact_volume'] += fact_volume
        totals['plan_income'] += plan_income
        totals['fact_income'] += fact_income
        totals['expected_income'] += expected_income

        report_data.append({
            'complex_name': complex_name,
            'plan_units': plan_units, 'fact_units': fact_units, 'percent_fact_units': percent_fact_units,
            'forecast_units': forecast_units,
            'plan_volume': plan_volume, 'fact_volume': fact_volume, 'percent_fact_volume': percent_fact_volume,
            'forecast_volume': forecast_volume,
            'plan_income': plan_income, 'fact_income': fact_income, 'percent_fact_income': percent_fact_income,
            'expected_income': expected_income
        })

    # Считаем итоговые проценты
    totals['percent_fact_units'] = (totals['fact_units'] / totals['plan_units']) * 100 if totals[
                                                                                              'plan_units'] > 0 else 0
    totals['forecast_units'] = ((totals['fact_units'] / passed_workdays) * workdays_in_month / totals[
        'plan_units']) * 100 if totals['plan_units'] > 0 else 0
    totals['percent_fact_volume'] = (totals['fact_volume'] / totals['plan_volume']) * 100 if totals[
                                                                                                 'plan_volume'] > 0 else 0
    totals['forecast_volume'] = ((totals['fact_volume'] / passed_workdays) * workdays_in_month / totals[
        'plan_volume']) * 100 if totals['plan_volume'] > 0 else 0
    totals['percent_fact_income'] = (totals['fact_income'] / totals['plan_income']) * 100 if totals[
                                                                                                 'plan_income'] > 0 else 0

    return report_data, totals  # Возвращаем два объекта: данные и итоги


def process_plan_from_excel(file_path: str, year: int, month: int):
    """Обрабатывает Excel-файл и загружает планы в БД."""
    df = pd.read_excel(file_path)

    for index, row in df.iterrows():
        plan_entry = SalesPlan.query.filter_by(
            year=year,
            month=month,
            complex_name=row['ЖК'],
            property_type=row['Тип недвижимости']
        ).first()

        if not plan_entry:
            plan_entry = SalesPlan(
                year=year,
                month=month,
                complex_name=row['ЖК'],
                property_type=row['Тип недвижимости']
            )
            db.session.add(plan_entry)

        # ИЗМЕНЕНИЕ: Считываем данные из новых колонок
        plan_entry.plan_units = row['План, шт']
        plan_entry.plan_volume = row['План контрактации, UZS']
        plan_entry.plan_income = row['План поступлений, UZS']

    db.session.commit()
    return f"Успешно обработано {len(df)} строк."


def generate_plan_template_excel():
    """Генерирует Excel-шаблон для загрузки планов."""
    print("[REPORT SERVICE] 📄 Генерация шаблона для плана продаж...")

    complex_names = get_all_complex_names()
    property_types = list(PropertyType)

    # ИЗМЕНЕНИЕ: Добавляем новые колонки в заголовки
    headers = ['ЖК', 'Тип недвижимости', 'План, шт', 'План контрактации, UZS', 'План поступлений, UZS']
    data = []

    for name in complex_names:
        for prop_type in property_types:
            row = {
                'ЖК': name,
                'Тип недвижимости': prop_type.value,
                'План, шт': 0,
                # ИЗМЕНЕНИЕ: Добавляем значения по умолчанию для новых колонок
                'План контрактации, UZS': 0,
                'План поступлений, UZS': 0
            }
            data.append(row)

    df = pd.DataFrame(data, columns=headers)

    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name='Шаблон плана')
    output.seek(0)

    print("[REPORT SERVICE] ✔️ Шаблон успешно сгенерирован.")
    return output


def get_monthly_summary_by_property_type(year: int, month: int):
    """Возвращает итоговые данные для каждого типа недвижимости (ШТУКИ + СУММЫ)."""
    summary_data = []
    property_types = list(PropertyType)

    # ... (код для расчета workdays без изменений) ...
    today = date.today()
    workdays_in_month = np.busday_count(f'{year}-{month:02d}-01',
                                        f'{year}-{month + 1:02d}-01' if month < 12 else f'{year + 1}-01-01')
    passed_workdays = np.busday_count(f'{year}-{month:02d}-01',
                                      today) if today.month == month and today.year == year else workdays_in_month
    passed_workdays = max(1, passed_workdays)

    for prop_type in property_types:
        # Штуки
        total_plan_units = sum(get_plan_data(year, month, prop_type.value).values())
        total_fact_units = sum(get_fact_data(year, month, prop_type.value).values())
        # Суммы
        total_plan_volume = sum(get_plan_volume_data(year, month, prop_type.value).values())
        total_fact_volume = sum(get_fact_volume_data(year, month, prop_type.value).values())

        if (total_plan_units + total_fact_units + total_plan_volume + total_fact_volume) == 0:
            continue

        # Считаем итоги по штукам
        dev_units = ((total_fact_units / total_plan_units) - 1) * 100 if total_plan_units > 0 else 0
        forecast_units = ((
                                      total_fact_units / passed_workdays) * workdays_in_month / total_plan_units) * 100 if total_plan_units > 0 else 0

        # Считаем итоги по суммам
        dev_volume = ((total_fact_volume / total_plan_volume) - 1) * 100 if total_plan_volume > 0 else 0
        forecast_volume = ((
                                       total_fact_volume / passed_workdays) * workdays_in_month / total_plan_volume) * 100 if total_plan_volume > 0 else 0

        summary_data.append({
            'property_type': prop_type.value,
            'total_plan_units': total_plan_units, 'total_fact_units': total_fact_units,
            'total_deviation_units': dev_units, 'total_forecast_units': forecast_units,
            'total_plan_volume': total_plan_volume, 'total_fact_volume': total_fact_volume,
            'total_deviation_volume': dev_volume, 'total_forecast_volume': forecast_volume
        })
    return summary_data


def get_fact_volume_data(year: int, month: int, property_type: str):
    """Собирает фактические данные о КОНТРАКТАЦИИ (сумма) из БД."""
    effective_date = func.coalesce(EstateDeal.agreement_date, EstateDeal.preliminary_date)

    results = db.session.query(
        EstateHouse.complex_name,
        func.sum(EstateDeal.deal_sum).label('fact_volume')  # Считаем СУММУ
    ).join(
        EstateSell, EstateDeal.estate_sell_id == EstateSell.id
    ).join(
        EstateHouse, EstateSell.house_id == EstateHouse.id
    ).filter(
        EstateDeal.deal_status_name.in_(["Сделка в работе", "Сделка проведена"]),
        extract('year', effective_date) == year,
        extract('month', effective_date) == month,
        EstateSell.estate_sell_category == property_type
    ).group_by(EstateHouse.complex_name).all()

    return {row.complex_name: (row.fact_volume or 0) for row in results}


def get_plan_volume_data(year: int, month: int, property_type: str):
    """Получает плановые данные по КОНТРАКТАЦИИ (сумма)."""
    results = SalesPlan.query.filter_by(
        year=year,
        month=month,
        property_type=property_type
    ).all()
    return {row.complex_name: row.plan_volume for row in results}