from datetime import date
from dateutil.relativedelta import relativedelta
import numpy_financial as npf
from flask import current_app
from app.services import selection_service, settings_service, currency_service
from app.models.discount_models import PaymentMethod
from app.services.discount_service import get_current_usd_rate

DEFAULT_RATE = 16.5 / 12 / 100
MAX_MORTGAGE_BODY = 420_000_000


def calculate_installment_plan(sell_id: int, term_months: int, additional_discounts: dict):
    """
    Рассчитывает сложную рассрочку.
    """
    settings = settings_service.get_calculator_settings()

    # ИЗМЕНЕНИЕ: Добавляем проверку на случай, если поле в настройках пустое
    whitelist_str = settings.standard_installment_whitelist or ""
    whitelist = [int(x.strip()) for x in whitelist_str.split(',') if x.strip()]
    if sell_id not in whitelist:
        raise ValueError("Этот вид рассрочки недоступен для данного объекта.")

    monthly_rate = settings.time_value_rate_annual / 12 / 100

    card_data = selection_service.get_apartment_card_data(sell_id)
    apartment_price = card_data.get('apartment', {}).get('estate_price', 0)
    discounts_100_payment = next((
        d for d in card_data.get('all_discounts_for_property_type', [])
        if d['payment_method'] == PaymentMethod.FULL_PAYMENT.value
    ), None)

    if not discounts_100_payment:
        raise ValueError("Скидки для 100% оплаты не найдены для этого объекта.")

    cadastre_date_str = discounts_100_payment.get('cadastre_date')
    if cadastre_date_str:
        cadastre_date = date.fromisoformat(cadastre_date_str)
        months_to_cadastre = relativedelta(cadastre_date, date.today()).months + relativedelta(cadastre_date,
                                                                                               date.today()).years * 12
        if term_months > months_to_cadastre:
            raise ValueError(f"Срок рассрочки не может превышать {months_to_cadastre} мес. (до кадастра)")
    elif term_months > 0:
        raise ValueError("Невозможно рассчитать рассрочку: не указана дата кадастра.")

    price_for_calc = apartment_price - 3_000_000

    total_discount_rate = 0
    total_discount_rate += discounts_100_payment.get('mpp', 0)
    total_discount_rate += discounts_100_payment.get('rop', 0)
    total_discount_rate += discounts_100_payment.get('action', 0)

    for disc_key, disc_value in additional_discounts.items():
        max_discount = discounts_100_payment.get(disc_key, 0)
        if disc_value > max_discount:
            raise ValueError(f"Скидка {disc_key.upper()} превышает максимум ({max_discount * 100}%)")
        total_discount_rate += disc_value

    price_after_discounts = price_for_calc * (1 - total_discount_rate)

    if term_months <= 0:
        raise ValueError("Срок рассрочки должен быть больше нуля.")

    monthly_payment = npf.pmt(monthly_rate, term_months, -price_after_discounts)

    calculated_contract_value = monthly_payment * term_months
    calculated_discount_percent = (1 - (calculated_contract_value / price_for_calc)) * 100 if price_for_calc > 0 else 0

    return {
        "price_list": apartment_price,
        "calculated_discount": calculated_discount_percent,
        "calculated_contract_value": calculated_contract_value,
        "monthly_payment": monthly_payment,
        "term_months": term_months
    }


def calculate_dp_installment_plan(sell_id: int, term_months: int, dp_amount: float, dp_type: str,
                                  additional_discounts: dict):
    """
    Рассчитывает рассрочку на Первоначальный Взнос (ПВ) с последующей ипотекой.
    """
    settings = settings_service.get_calculator_settings()

    # ИЗМЕНЕНИЕ: Добавляем проверку на случай, если поле в настройках пустое
    whitelist_str = settings.dp_installment_whitelist or ""
    whitelist = [int(x.strip()) for x in whitelist_str.split(',') if x.strip()]
    if sell_id not in whitelist:
        raise ValueError("Этот вид оплаты недоступен для данного объекта.")

    if not (1 <= term_months <= settings.dp_installment_max_term):
        raise ValueError(f"Срок рассрочки на ПВ должен быть от 1 до {settings.dp_installment_max_term} месяцев.")

    monthly_rate = settings.time_value_rate_annual / 12 / 100

    card_data = selection_service.get_apartment_card_data(sell_id)
    apartment_price = card_data.get('apartment', {}).get('estate_price', 0)

    discounts_mortgage = next((
        d for d in card_data.get('all_discounts_for_property_type', [])
        if d['payment_method'] == PaymentMethod.MORTGAGE.value
    ), None)

    if not discounts_mortgage:
        raise ValueError("Скидки для ипотеки не найдены для этого объекта.")

    price_for_calc = apartment_price - 3_000_000

    total_discount_rate = 0
    total_discount_rate += discounts_mortgage.get('mpp', 0)
    total_discount_rate += discounts_mortgage.get('rop', 0)
    total_discount_rate += discounts_mortgage.get('action', 0)

    for disc_key, disc_value in additional_discounts.items():
        max_discount = discounts_mortgage.get(disc_key, 0)
        if disc_value > max_discount:
            raise ValueError(f"Скидка {disc_key.upper()} превышает максимум ({max_discount * 100}%)")
        total_discount_rate += disc_value

    price_after_discounts = price_for_calc * (1 - total_discount_rate)

    usd_rate = get_current_usd_rate() or currency_service.get_current_effective_rate()

    if dp_type == 'percent':
        dp_uzs = price_after_discounts * (dp_amount / 100)
    elif dp_type == 'usd':
        dp_uzs = dp_amount * usd_rate
    else:
        dp_uzs = dp_amount

    min_dp = price_after_discounts * 0.15
    if dp_uzs < min_dp:
        raise ValueError(f"Первоначальный взнос не может быть меньше 15% ({min_dp:,.0f} UZS).")

    mortgage_body = price_after_discounts - dp_uzs
    if mortgage_body > MAX_MORTGAGE_BODY:
        increase_needed_uzs = mortgage_body - MAX_MORTGAGE_BODY
        if dp_type == 'percent':
            increase_needed_val = (increase_needed_uzs / price_after_discounts) * 100
            msg = f"Тело ипотеки превышает лимит. Увеличьте ПВ на {increase_needed_val:.2f}%."
        elif dp_type == 'usd':
            increase_needed_val = increase_needed_uzs / usd_rate
            msg = f"Тело ипотеки превышает лимит. Увеличьте ПВ на ${increase_needed_val:,.0f}."
        else:
            msg = f"Тело ипотеки превышает лимит. Увеличьте ПВ на {increase_needed_uzs:,.0f} UZS."
        raise ValueError(msg)

    monthly_payment_for_dp = npf.pmt(monthly_rate, term_months, -dp_uzs)
    calculated_down_payment_value = monthly_payment_for_dp * term_months
    calculated_contract_value = calculated_down_payment_value + mortgage_body
    calculated_discount_percent = (1 - (calculated_contract_value / price_for_calc)) * 100 if price_for_calc > 0 else 0

    return {
        "term_months": term_months,
        "monthly_payment_for_dp": monthly_payment_for_dp,
        "mortgage_body": mortgage_body,
        "calculated_contract_value": calculated_contract_value,
        "calculated_discount": calculated_discount_percent
    }