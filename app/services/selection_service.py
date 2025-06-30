from flask import current_app, abort
from sqlalchemy.orm import joinedload
from ..core.extensions import db
from ..models.estate_models import EstateHouse, EstateSell
from ..models.discount_models import Discount, DiscountVersion, PaymentMethod, PropertyType
import json  # Убедитесь, что эта строка есть!
from datetime import date  # Убедитесь, что date импортирован для .isoformat()

from ..models.exclusion_models import ExcludedSell

VALID_STATUSES = ["Маркетинговый резерв", "Подбор"]
DEDUCTION_AMOUNT = 3_000_000
MAX_MORTGAGE = 420_000_000
MIN_INITIAL_PAYMENT_PERCENT = 0.15


def find_apartments_by_budget(budget: float, currency: str, property_type_str: str, floor: str = None,
                              rooms: str = None, payment_method: str = None):
    """
    Финальная версия с исправленной логикой области видимости переменной discount.
    """
    usd_rate = current_app.config.get('USD_TO_UZS_RATE', 12650.0)
    budget_uzs = budget * usd_rate if currency.upper() == 'USD' else budget

    print("\n" + "=" * 50)
    print(
        f"[SELECTION_SERVICE] 🔎 Поиск запущен. Бюджет: {budget} {currency} ({budget_uzs:,.0f} UZS). Тип: {property_type_str}")
    print(
        f"[SELECTION_SERVICE] Фильтры: Этаж='{floor or 'Любой'}', Комнат='{rooms or 'Любой'}', Оплата='{payment_method or 'Любая'}'")
    print("=" * 50)

    active_version = DiscountVersion.query.filter_by(is_active=True).first()
    if not active_version:
        print("[SELECTION_SERVICE] ❌ Не найдена активная версия скидок. Поиск прерван.")
        return {}

    property_type_enum = PropertyType(property_type_str)

    discounts_map = {
        (d.complex_name, d.payment_method): d
        for d in Discount.query.filter_by(version_id=active_version.id, property_type=property_type_enum).all()
    }
    excluded_sell_ids = {e.sell_id for e in ExcludedSell.query.all()}
    print(f"[SELECTION_SERVICE] Исключенные ID квартир: {excluded_sell_ids}")
    query = db.session.query(EstateSell).options(
        joinedload(EstateSell.house)
    ).filter(
        EstateSell.estate_sell_category == property_type_enum.value,
        EstateSell.estate_sell_status_name.in_(VALID_STATUSES),
        EstateSell.estate_price.isnot(None),
        EstateSell.estate_price > DEDUCTION_AMOUNT,
        EstateSell.id.notin_(excluded_sell_ids) if excluded_sell_ids else True
    )

    if floor and floor.isdigit():
        query = query.filter(EstateSell.estate_floor == int(floor))

    if rooms and rooms.isdigit():
        query = query.filter(EstateSell.estate_rooms == int(rooms))

    available_sells = query.all()

    print(f"[SELECTION_SERVICE] Найдено квартир по фильтрам до расчета скидок: {len(available_sells)}")

    results = {}
    default_discount = Discount()

    payment_methods_to_check = list(PaymentMethod)
    if payment_method:
        selected_pm_enum = next((pm for pm in PaymentMethod if pm.value == payment_method), None)
        if selected_pm_enum:
            payment_methods_to_check = [selected_pm_enum]

    for sell in available_sells:
        if not sell.house: continue

        complex_name = sell.house.complex_name
        base_price = sell.estate_price

        for payment_method_enum in payment_methods_to_check:
            is_match = False
            apartment_details = {}
            price_after_deduction = base_price - DEDUCTION_AMOUNT

            discount = discounts_map.get((complex_name, payment_method_enum), default_discount)

            if payment_method_enum == PaymentMethod.FULL_PAYMENT:
                total_discount_rate = (discount.mpp or 0) + (discount.rop or 0) + (discount.action or 0)
                final_price_uzs = price_after_deduction * (1 - total_discount_rate)
                if budget_uzs >= final_price_uzs:
                    is_match = True
                    apartment_details = {"final_price": final_price_uzs}

            elif payment_method_enum == PaymentMethod.MORTGAGE:
                total_discount_rate = (discount.mpp or 0) + (discount.rop or 0) + (discount.action or 0)
                price_after_discounts = price_after_deduction * (1 - total_discount_rate)

                initial_payment_uzs = price_after_discounts - MAX_MORTGAGE
                min_required_payment_uzs = price_after_discounts * MIN_INITIAL_PAYMENT_PERCENT

                if initial_payment_uzs >= min_required_payment_uzs and budget_uzs >= initial_payment_uzs:
                    is_match = True
                    apartment_details = {"final_price": price_after_discounts, "initial_payment": initial_payment_uzs}

            if is_match:
                pv_log = apartment_details.get('initial_payment') or apartment_details['final_price']
                print(
                    f"    ✔️  Подходит квартира ID {sell.id} ({sell.estate_rooms} комн). Цена со скидкой: {apartment_details['final_price']:,.0f} UZS. Требуемый первый взнос: {pv_log:,.0f} UZS")

                results.setdefault(complex_name, {"total_matches": 0, "by_payment_method": {}})
                payment_method_str = payment_method_enum.value
                results[complex_name]["by_payment_method"].setdefault(payment_method_str, {"total": 0, "by_rooms": {}})
                rooms_str = str(sell.estate_rooms) if sell.estate_rooms else "Студия"
                results[complex_name]["by_payment_method"][payment_method_str]["by_rooms"].setdefault(rooms_str, [])

                details = {"id": sell.id, "floor": sell.estate_floor, "area": sell.estate_area,
                           "base_price": base_price, **apartment_details}

                results[complex_name]["by_payment_method"][payment_method_str]["by_rooms"][rooms_str].append(details)
                results[complex_name]["by_payment_method"][payment_method_str]["total"] += 1
                results[complex_name]["total_matches"] += 1

    print(f"[SELECTION_SERVICE] ✅ Поиск завершен. Найдено совпадений в комплексах: {list(results.keys())}")
    print("=" * 50 + "\n")
    return results


def get_apartment_card_data(sell_id: int):
    """
    Собирает все данные для детальной карточки квартиры, включая все варианты оплаты
    и максимальные значения дополнительных скидок для JavaScript.
    """
    # ... (начало функции, получение sell, active_version, property_type_enum - без изменений) ...
    sell = db.session.query(EstateSell).options(joinedload(EstateSell.house)).filter_by(id=sell_id).first()
    if not sell:
        abort(404)

    active_version = DiscountVersion.query.filter_by(is_active=True).first()
    if not active_version:
        return {'apartment': {}, 'pricing': [], 'all_discounts_for_property_type': []}

    try:
        property_type_enum = PropertyType(sell.estate_sell_category)
    except ValueError:
        return {'apartment': {}, 'pricing': [], 'all_discounts_for_property_type': []}

    all_discounts_for_property_type = Discount.query.filter_by(
        version_id=active_version.id,
        property_type=property_type_enum,
        complex_name=sell.house.complex_name
    ).all()

    # ... (сериализация скидок и данных о квартире - без изменений) ...
    serialized_discounts = []
    for d in all_discounts_for_property_type:
        serialized_discounts.append({
            'complex_name': d.complex_name,
            'property_type': d.property_type.value,
            'payment_method': d.payment_method.value,
            'mpp': d.mpp if d.mpp is not None else 0.0,
            'rop': d.rop if d.rop is not None else 0.0,
            'kd': d.kd if d.kd is not None else 0.0,
            'opt': d.opt if d.opt is not None else 0.0,
            'gd': d.gd if d.gd is not None else 0.0,
            'holding': d.holding if d.holding is not None else 0.0,
            'shareholder': d.shareholder if d.shareholder is not None else 0.0,
            'action': d.action if d.action is not None else 0.0,
            'cadastre_date': d.cadastre_date.isoformat() if d.cadastre_date else None
        })

    serialized_house = {
        'id': sell.house.id,
        'complex_name': sell.house.complex_name,
        'name': sell.house.name,
        'geo_house': sell.house.geo_house
    } if sell.house else {}

    serialized_apartment = {
        'id': sell.id,
        'house_id': sell.house_id,
        'estate_sell_category': sell.estate_sell_category,
        'estate_floor': sell.estate_floor,
        'estate_rooms': sell.estate_rooms,
        'estate_price_m2': sell.estate_price_m2,
        'estate_sell_status_name': sell.estate_sell_status_name,
        'estate_price': sell.estate_price,
        'estate_area': sell.estate_area,
        'house': serialized_house
    }
    # --- НАЧАЛО ИЗМЕНЕНИЙ В ЛОГИКЕ РАСЧЕТА ---

    discounts_map = {
        (d['complex_name'], PaymentMethod(d['payment_method'])): d
        for d in serialized_discounts
    }

    pricing_options = []  # <-- Здесь будем хранить все 4 варианта
    base_price = serialized_apartment['estate_price']
    price_after_deduction = base_price - DEDUCTION_AMOUNT

    # --- 1. Расчет для "100% оплата" и "Легкий старт (100% оплата)" ---
    pm_full_payment = PaymentMethod.FULL_PAYMENT
    discount_data_100 = discounts_map.get((serialized_house['complex_name'], pm_full_payment))

    if discount_data_100:
        mpp_val = discount_data_100.get('mpp', 0.0)
        rop_val = discount_data_100.get('rop', 0.0)

        # Расчет для "Легкий старт (100% оплата)" - БЕЗ КД
        rate_easy_start_100 = mpp_val + rop_val
        price_easy_start_100 = price_after_deduction * (1 - rate_easy_start_100)
        pricing_options.append({
            "payment_method": "Легкий старт (100% оплата)",
            "type_key": "easy_start_100",  # Уникальный ключ для фронтенда
            "base_price": base_price,
            "deduction": DEDUCTION_AMOUNT,
            "price_after_deduction": price_after_deduction,
            "final_price": price_easy_start_100,
            "initial_payment": None,
            "mortgage_body": None,
            "discounts": [{"name": "МПП", "value": mpp_val}, {"name": "РОП", "value": rop_val}]
        })

    # --- 2. Расчет для "Ипотека" и "Легкий старт (ипотека)" ---
    pm_mortgage = PaymentMethod.MORTGAGE
    discount_data_mortgage = discounts_map.get((serialized_house['complex_name'], pm_mortgage))

    if discount_data_mortgage:
        mpp_val = discount_data_mortgage.get('mpp', 0.0)
        rop_val = discount_data_mortgage.get('rop', 0.0)

        # Расчет для "Легкий старт (ипотека)" - БЕЗ КД
        rate_easy_start_mortgage = mpp_val + rop_val
        price_for_easy_mortgage = price_after_deduction * (1 - rate_easy_start_mortgage)

        initial_payment_easy = price_for_easy_mortgage - MAX_MORTGAGE
        min_required_payment_easy = price_for_easy_mortgage * MIN_INITIAL_PAYMENT_PERCENT

        if initial_payment_easy < 0: initial_payment_easy = 0
        if initial_payment_easy < min_required_payment_easy: initial_payment_easy = min_required_payment_easy

        final_price_easy_mortgage = initial_payment_easy + MAX_MORTGAGE

        pricing_options.append({
            "payment_method": "Легкий старт (ипотека)",
            "type_key": "easy_start_mortgage",  # Уникальный ключ
            "base_price": base_price,
            "deduction": DEDUCTION_AMOUNT,
            "price_after_deduction": price_after_deduction,
            "final_price": final_price_easy_mortgage,
            "initial_payment": initial_payment_easy,
            "mortgage_body": MAX_MORTGAGE,
            "discounts": [{"name": "МПП", "value": mpp_val}, {"name": "РОП", "value": rop_val}]
        })

    # --- 3. Добавляем стандартные калькуляторы (они уже есть в коде, можно просто скопировать и адаптировать) ---
    for payment_method_enum in PaymentMethod:
        discount_data_for_method = discounts_map.get((serialized_house['complex_name'], payment_method_enum))
        mpp_val = discount_data_for_method.get('mpp', 0.0) if discount_data_for_method else 0.0
        rop_val = discount_data_for_method.get('rop', 0.0) if discount_data_for_method else 0.0

        option_details = {
            "payment_method": payment_method_enum.value,
            "type_key": payment_method_enum.name.lower(),  # Ключ для стандартных типов
            "base_price": base_price,
            "deduction": DEDUCTION_AMOUNT,
            "price_after_deduction": price_after_deduction,
            "final_price": None,
            "initial_payment": None,
            "mortgage_body": None,
            "discounts": []
        }

        if payment_method_enum == PaymentMethod.FULL_PAYMENT:
            total_discount_rate = mpp_val + rop_val
            final_price = price_after_deduction * (1 - total_discount_rate)
            option_details["final_price"] = final_price
            option_details["discounts"] = [{"name": "МПП", "value": mpp_val}, {"name": "РОП", "value": rop_val}]

        elif payment_method_enum == PaymentMethod.MORTGAGE:
            total_discount_rate = mpp_val + rop_val
            final_price = price_after_deduction * (1 - total_discount_rate)
            initial_payment = final_price - MAX_MORTGAGE
            if initial_payment < 0: initial_payment = 0
            min_required_payment = final_price * MIN_INITIAL_PAYMENT_PERCENT
            if initial_payment < min_required_payment: initial_payment = min_required_payment

            final_price_mortgage = initial_payment + MAX_MORTGAGE
            option_details["final_price"] = final_price_mortgage
            option_details["initial_payment"] = initial_payment
            option_details["mortgage_body"] = MAX_MORTGAGE
            option_details["discounts"] = [{"name": "МПП", "value": mpp_val}, {"name": "РОП", "value": rop_val}]

        if option_details["final_price"] is not None:
            pricing_options.append(option_details)

    return {
        'apartment': serialized_apartment,
        'pricing': pricing_options,
        'all_discounts_for_property_type': serialized_discounts
    }