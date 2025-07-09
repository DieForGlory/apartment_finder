from flask import Blueprint, request, make_response
from flask_restx import Api, Resource, fields, reqparse
import json
from flask import request
# Импортируем все необходимые сервисы
from app.services import (
    selection_service,
    report_service,
    inventory_service,
    currency_service
)
from app.models.discount_models import PropertyType  # Для получения списка типов недвижимости
from app.services import discount_service
# 1. Создаем Blueprint
api_bp = Blueprint('api', __name__, url_prefix="api")

# 2. Инициализируем Flask-RESTx
api = Api(
    api_bp,
    version='1.0',
    title='ApartmentFinder API',
    description='API для мобильного приложения и внешних интеграций',
    doc='/docs/'
)

# ===================================================================
#          ПРОСТРАНСТВО ИМЕН ДЛЯ ПОДБОРА КВАРТИР
# ===================================================================
apartments_ns = api.namespace('apartments', description='Операции с квартирами')

search_model = apartments_ns.model('ApartmentSearchInput', {
    'budget': fields.Float(required=True, description='Сумма клиента', example=50000),
    'currency': fields.String(required=True, description='Валюта', enum=['USD', 'UZS'], example='USD'),
    'property_type_str': fields.String(required=True, description='Тип недвижимости', example='Квартира'),
    'floor': fields.String(description='Желаемый этаж', example='5'),
    'rooms': fields.String(description='Желаемое кол-во комнат', example='2'),
    'payment_method': fields.String(description='Вид оплаты', example='Ипотека')
})


@apartments_ns.route('/search')
class ApartmentSearchResource(Resource):
    @apartments_ns.expect(search_model, validate=True)
    def post(self):
        data = api.payload
        """Поиск квартир по бюджету и другим критериям"""
        raw_data = request.get_data(as_text=True)
        if not raw_data:
            return {'message': 'Тело запроса пустое'}, 400

        # Преобразуем текстовую строку JSON в словарь Python
        try:
            data = json.loads(raw_data)
        except json.JSONDecodeError:
            return {'message': 'Некорректный формат JSON в теле запроса'}, 400
        results = selection_service.find_apartments_by_budget(
            budget=data.get('budget'),
            currency=data.get('currency'),
            property_type_str=data.get('property_type_str'),
            floor=data.get('floor'),
            rooms=data.get('rooms'),
            payment_method=data.get('payment_method')
        )
        return results


@apartments_ns.route('/<int:sell_id>')
@apartments_ns.response(404, 'Квартира не найдена')
@apartments_ns.param('sell_id', 'Идентификатор квартиры')
class ApartmentResource(Resource):
    def get(self, sell_id):
        """Получение детальной информации по ID квартиры"""
        card_data = selection_service.get_apartment_card_data(sell_id)
        if not card_data or not card_data.get('apartment'):
            return {'message': 'Квартира с таким ID не найдена'}, 404
        return card_data


# ===================================================================
#          НОВОЕ ПРОСТРАНСТВО ИМЕН ДЛЯ ОТЧЕТНОСТИ
# ===================================================================
reports_ns = api.namespace('reports', description='Получение аналитических отчетов')

# --- План-факт отчет ---
plan_fact_parser = reqparse.RequestParser()
plan_fact_parser.add_argument('year', type=int, required=True, help='Год отчета', location='args')
plan_fact_parser.add_argument('month', type=int, required=True, help='Месяц отчета', location='args')
plan_fact_parser.add_argument('property_type', type=str, required=True, help='Тип недвижимости',
                              choices=[pt.value for pt in PropertyType], location='args')


@reports_ns.route('/plan-fact')
class PlanFactReportResource(Resource):
    @reports_ns.expect(plan_fact_parser)
    def get(self):
        """Возвращает детальный план-факт отчет"""
        args = plan_fact_parser.parse_args()

        report_data, totals = report_service.generate_plan_fact_report(
            args['year'], args['month'], args['property_type']
        )
        grand_totals = report_service.calculate_grand_totals(args['year'], args['month'])

        return {
            'details': report_data,
            'totals_by_type': totals,
            'grand_totals': grand_totals
        }


# --- Сводка по товарному запасу ---
inventory_parser = reqparse.RequestParser()
inventory_parser.add_argument('currency', type=str, default='UZS', choices=['UZS', 'USD'],
                              help='Валюта для отображения денежных значений', location='args')


@reports_ns.route('/inventory-summary')
class InventorySummaryResource(Resource):
    @reports_ns.expect(inventory_parser)
    def get(self):
        """Возвращает сводку по товарному запасу"""
        args = inventory_parser.parse_args()
        selected_currency = args['currency']

        summary_by_complex, overall_summary = inventory_service.get_inventory_summary_data()

        # Если запросили USD, конвертируем денежные значения
        if selected_currency == 'USD':
            usd_rate = currency_service.get_current_effective_rate()
            if usd_rate > 0:
                # Конвертируем общую сводку
                for metrics in overall_summary.values():
                    metrics['total_value'] /= usd_rate
                    metrics['avg_price_m2'] /= usd_rate
                # Конвертируем детализацию по ЖК
                for complex_data in summary_by_complex.values():
                    for metrics in complex_data.values():
                        metrics['total_value'] /= usd_rate
                        metrics['avg_price_m2'] /= usd_rate

        return {
            'overall_summary': overall_summary,
            'summary_by_complex': summary_by_complex
        }

discounts_ns = api.namespace('discounts', description='Просмотр системы скидок')

@discounts_ns.route('/overview')
class DiscountOverviewResource(Resource):
    @discounts_ns.doc('get_discounts_overview')
    def get(self):
        """Возвращает полную информацию по действующей системе скидок"""
        discounts_data = discount_service.get_discounts_with_summary()
        if not discounts_data:
            return {'message': 'Активная система скидок не найдена или пуста'}, 404
        return discounts_data