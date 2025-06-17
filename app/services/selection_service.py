from flask import current_app
from sqlalchemy.orm import joinedload
from ..core.extensions import db
from ..models.estate_models import EstateSell
from ..models.discount_models import Discount, DiscountVersion, PaymentMethod, PropertyType

VALID_STATUSES = ["Маркетинговый резерв", "Подбор"]
DEDUCTION_AMOUNT = 3_000_000
MAX_MORTGAGE = 420_000_000
MIN_INITIAL_PAYMENT_PERCENT = 0.15


def find_apartments_by_budget(budget: float, currency: str, property_type_str: str):
    """
    Финальная версия с исправленной логикой области видимости переменной discount.
    """
    usd_rate = current_app.config.get('USD_TO_UZS_RATE', 12650.0)
    budget_uzs = budget * usd_rate if currency.upper() == 'USD' else budget
    print(f"Поиск запущен. Бюджет: {budget} {currency} ({budget_uzs:,.0f} UZS). Тип: {property_type_str}")

    active_version = DiscountVersion.query.filter_by(is_active=True).first()
    if not active_version: return {}

    property_type_enum = PropertyType(property_type_str)

    discounts_map = {
        (d.complex_name, d.payment_method): d
        for d in Discount.query.filter_by(version_id=active_version.id, property_type=property_type_enum).all()
    }

    available_sells = db.session.query(EstateSell).options(
        joinedload(EstateSell.house)
    ).filter(
        EstateSell.estate_sell_category == property_type_str,
        EstateSell.estate_sell_status_name.in_(VALID_STATUSES),
        EstateSell.estate_price.isnot(None),
        EstateSell.estate_price > DEDUCTION_AMOUNT
    ).all()

    results = {}
    default_discount = Discount()

    for sell in available_sells:
        if not sell.house: continue

        complex_name = sell.house.complex_name
        base_price = sell.estate_price

        for payment_method_enum in PaymentMethod:
            is_match = False
            apartment_details = {}
            price_after_deduction = base_price - DEDUCTION_AMOUNT

            # --- ИСПРАВЛЕНИЕ: Переменная discount определяется в начале цикла ---
            # Это гарантирует ее существование для всех блоков if/elif.
            discount = discounts_map.get((complex_name, payment_method_enum), default_discount)

            if payment_method_enum == PaymentMethod.FULL_PAYMENT:
                total_discount_rate = (discount.mpp or 0) + (discount.rop or 0) + (discount.kd or 0)
                final_price_uzs = price_after_deduction * (1 - total_discount_rate)
                if budget_uzs >= final_price_uzs:
                    is_match = True;
                    apartment_details = {"final_price": final_price_uzs}

            elif payment_method_enum == PaymentMethod.MORTGAGE:
                total_discount_rate = (discount.mpp or 0) + (discount.rop or 0) + (discount.kd or 0)
                price_after_discounts = price_after_deduction * (1 - total_discount_rate)
                initial_payment_uzs = price_after_discounts - MAX_MORTGAGE
                min_required_payment_uzs = price_after_discounts * MIN_INITIAL_PAYMENT_PERCENT
                if initial_payment_uzs >= min_required_payment_uzs and budget_uzs >= initial_payment_uzs:
                    is_match = True;
                    apartment_details = {"final_price": price_after_discounts, "initial_payment": initial_payment_uzs}

            elif payment_method_enum == PaymentMethod.TRANCHE_100:
                base_discount = discounts_map.get((complex_name, PaymentMethod.FULL_PAYMENT), default_discount)
                total_discount_rate = (base_discount.mpp or 0) + (base_discount.rop or 0)
                final_price_uzs = price_after_deduction * (1 - total_discount_rate)
                first_tranche_uzs = final_price_uzs / 3
                if budget_uzs >= final_price_uzs:
                    is_match = True;
                    apartment_details = {"final_price": final_price_uzs, "first_tranche": first_tranche_uzs}

            elif payment_method_enum == PaymentMethod.TRANCHE_MORTGAGE:
                base_discount = discounts_map.get((complex_name, PaymentMethod.MORTGAGE), default_discount)
                total_discount_rate = (base_discount.mpp or 0) + (base_discount.rop or 0)
                price_after_discounts = price_after_deduction * (1 - total_discount_rate)
                initial_payment_uzs = price_after_discounts - MAX_MORTGAGE
                min_required_payment_uzs = price_after_discounts * MIN_INITIAL_PAYMENT_PERCENT
                if initial_payment_uzs >= min_required_payment_uzs:
                    first_tranche_pv_uzs = initial_payment_uzs / 3
                    if budget_uzs >= initial_payment_uzs:
                        is_match = True;
                        apartment_details = {"final_price": price_after_discounts,
                                             "initial_payment": initial_payment_uzs,
                                             "first_tranche": first_tranche_pv_uzs}

            if is_match:
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

    print("Поиск завершен.")
    return results