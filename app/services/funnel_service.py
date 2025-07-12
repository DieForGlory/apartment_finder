# app/services/funnel_service.py
from datetime import date
from sqlalchemy import func, distinct
from app.core.extensions import db
from app.models.funnel_models import EstateBuy, EstateBuysStatusLog
from collections import defaultdict


def _format_status(status, custom_status):
    """Вспомогательная функция для чистого отображения имени статуса."""
    status = (status or "").strip()
    custom_status = (custom_status or "").strip()
    if not status:
        return "Без статуса"
    return f"{status}: {custom_status}" if custom_status else status


def finalize_tree(node, threshold_percent=1.0):
    """
    Рекурсивно обходит дерево, начиная с листьев, упрощает его,
    группируя редкие ветки, и преобразует дочерние узлы в отсортированный список.
    """
    if not node.get('children'):
        node['children'] = []
        return

    for child_node in node['children'].values():
        finalize_tree(child_node, threshold_percent)

    children_list = list(node['children'].values())
    threshold_count = (node['count'] * threshold_percent) / 100.0

    main_children = [child for child in children_list if child['count'] >= threshold_count]
    other_children = [child for child in children_list if child['count'] < threshold_count]

    if len(other_children) > 1:
        other_count = sum(child['count'] for child in other_children)
        other_node = {'name': 'Прочие пути', 'count': other_count, 'children': []}
        main_children.append(other_node)
    else:
        main_children.extend(other_children)

    node['children'] = sorted(main_children, key=lambda x: x['count'], reverse=True)


def get_funnel_data(start_date_str: str, end_date_str: str):
    """
    Строит полное дерево путей заявок, созданных в указанный период.
    """
    # === Шаг 1: Когорта по ДАТЕ СОЗДАНИЯ заявки ===
    cohort_query = db.session.query(EstateBuy.id)
    if start_date_str:
        try:
            start_date = date.fromisoformat(start_date_str)
            cohort_query = cohort_query.filter(EstateBuy.date_added >= start_date)
        except (ValueError, TypeError):
            pass
    if end_date_str:
        try:
            end_date = date.fromisoformat(end_date_str)
            cohort_query = cohort_query.filter(EstateBuy.date_added <= end_date)
        except (ValueError, TypeError):
            pass

    # --- ИЗМЕНЕНИЕ 1: Считаем общее количество напрямую из запроса ---
    trunk_count = cohort_query.count()

    if not trunk_count:
        return {'name': 'Заявки, созданные за период', 'count': 0, 'children': []}, {}

    # === Шаг 2: Получаем все логи для когорты, используя cohort_query как ПОДЗАПРОС ===
    # --- ИЗМЕНЕНИЕ 2: Вместо списка ID передаем сам объект запроса ---
    logs = db.session.query(
        EstateBuysStatusLog.estate_buy_id,
        EstateBuysStatusLog.status_to_name,
        EstateBuysStatusLog.status_custom_to_name
    ).filter(EstateBuysStatusLog.estate_buy_id.in_(cohort_query)).order_by(  # <--- ЭФФЕКТИВНЫЙ ПОДЗАПРОС
        EstateBuysStatusLog.estate_buy_id, EstateBuysStatusLog.log_date
    ).all()

    # === Шаг 3: Восстанавливаем путь для каждой заявки (без изменений) ===
    paths_by_buy_id = defaultdict(list)
    for log in logs:
        formatted_status = _format_status(log.status_to_name, log.status_custom_to_name)
        if not paths_by_buy_id[log.estate_buy_id] or paths_by_buy_id[log.estate_buy_id][-1] != formatted_status:
            paths_by_buy_id[log.estate_buy_id].append(formatted_status)

    # === Шаг 4: Строим древовидную структуру из путей (без изменений) ===
    tree = {'name': 'Заявки, созданные за период', 'count': trunk_count, 'children': {}}
    for path in paths_by_buy_id.values():
        current_level = tree
        for stage in path:
            if stage not in current_level['children']:
                current_level['children'][stage] = {'name': stage, 'count': 0, 'children': {}}
            current_level['children'][stage]['count'] += 1
            current_level = current_level['children'][stage]

    # === Шаг 5: Вызываем единую функцию для финальной обработки дерева (без изменений) ===
    finalize_tree(tree)

    return tree, {}