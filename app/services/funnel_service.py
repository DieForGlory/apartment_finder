# app/services/funnel_service.py
from datetime import date
from sqlalchemy import func, cast, Date
from app.core.extensions import db
from app.models.funnel_models import EstateBuy, EstateBuysStatusLog


def get_funnel_data(start_date_str: str = None, end_date_str: str = None):
    """
    Финальная версия, реализующая пошаговый когортный анализ
    с использованием одного подзапроса для максимальной надежности.
    """
    # === Шаг 1: Находим ID заявок из КОГОРТЫ по дате СОЗДАНИЯ ===
    cohort_query = db.session.query(EstateBuy.id)
    if start_date_str:
        try:
            cohort_query = cohort_query.filter(EstateBuy.date_added >= date.fromisoformat(start_date_str))
        except (ValueError, TypeError):
            pass
    if end_date_str:
        try:
            cohort_query = cohort_query.filter(EstateBuy.date_added <= date.fromisoformat(end_date_str))
        except (ValueError, TypeError):
            pass

    trunk_count = cohort_query.count()
    if not trunk_count:
        return {}, {}  # Возвращаем пустые словари, если нет данных

    # Создаем подзапрос из ID нашей когорты, который будем использовать во всех последующих запросах
    cohort_subquery = cohort_query.subquery()

    # === Вспомогательная функция для подсчета уникальных заявок ===
    def count_unique_bids(status_name, custom_status_name=None):
        q = db.session.query(func.count(func.distinct(EstateBuysStatusLog.estate_buy_id))) \
            .filter(EstateBuysStatusLog.estate_buy_id.in_(cohort_subquery))  # Всегда фильтруем по основной когорте

        # Фильтры по статусу и подстатусу без очистки
        q = q.filter(EstateBuysStatusLog.status_to_name == status_name)
        if custom_status_name:
            q = q.filter(EstateBuysStatusLog.status_custom_to_name == custom_status_name)

        return q.scalar() or 0

    # === Шаг 2: Считаем каждую ветку для нашей когорты ===
    count_non_target = count_unique_bids(status_name='Нецелевой')
    count_proverka = count_unique_bids(status_name='Проверка')

    # "Ожидание звонка" - это подстатус "Проверки", поэтому ищем его с этим основным статусом
    count_waiting_call = count_unique_bids(status_name='Проверка', custom_status_name='Ожидание Звонка')

    # "Подбор" и его подстатусы
    count_podbor_total = count_unique_bids(status_name='Подбор')
    count_meeting_scheduled = count_unique_bids(status_name='Подбор', custom_status_name='Назначенная встреча')
    count_visit_occurred = count_unique_bids(status_name='Подбор', custom_status_name='Визит состоялся ')
    count_visit_failed = count_unique_bids(status_name='Подбор', custom_status_name='Визит не состоялся')
    count_otkaz = count_unique_bids(status_name='Отказ')  # Отказ считается для всей когорты

    # === Шаг 3: Собираем итоговую структуру ===
    funnel_data = {
        'trunk': {'name': 'Всего заявок создано', 'count': trunk_count},
        'main_branches': [
            {'name': 'Перешли в "Нецелевой"', 'count': count_non_target},
            {
                'name': 'Перешли в "Проверку"',
                'count': count_proverka,
                'sub_branches': [
                    {'name': 'Ожидание звонка', 'count': count_waiting_call},
                ]
            },
            {
                'name': 'Перешли в "Подбор"',
                'count': count_podbor_total,
                'sub_branches': [
                    {'name': 'Назначена встреча', 'count': count_meeting_scheduled},
                    {'name': 'Визит состоялся', 'count': count_visit_occurred},
                    {'name': 'Визит не состоялся', 'count': count_visit_failed},
                ]
            },
            {'name': 'Отказ', 'count': count_otkaz},
        ]
    }

    # Возвращаем только одну воронку, как и ожидает ваш шаблон
    return funnel_data, {}