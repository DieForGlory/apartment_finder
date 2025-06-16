from datetime import date
from sqlalchemy.orm import joinedload
from ..core.extensions import db
from ..models.discount_models import Discount, PropertyType, PaymentMethod
from ..models.estate_models import EstateSell
import pandas as pd
import io
import copy


# --- Вспомогательные функции (process_discounts_from_excel, и т.д.) остаются без изменений ---

def _normalize_percentage(value):
    try:
        num_value = float(value)
        if num_value > 1.0: return num_value / 100.0
        return num_value
    except (ValueError, TypeError):
        return 0.0


def process_discounts_from_excel(file_path):
    print(f"\n[DISCOUNT SERVICE] Начало обработки файла: {file_path}")
    df = pd.read_excel(file_path)
    created_count, updated_count = 0, 0
    for index, row in df.iterrows():
        discount = Discount.query.filter_by(
            complex_name=row['ЖК'],
            property_type=PropertyType(row['Тип недвижимости']),
            payment_method=PaymentMethod(row['Тип оплаты'])
        ).first()
        if not discount:
            discount = Discount(complex_name=row['ЖК'], property_type=PropertyType(row['Тип недвижимости']),
                                payment_method=PaymentMethod(row['Тип оплаты']))
            db.session.add(discount)
            created_count += 1
        else:
            updated_count += 1
        discount.mpp = _normalize_percentage(row.get('МПП'))
        discount.rop = _normalize_percentage(row.get('РОП'))
        discount.kd = _normalize_percentage(row.get('КД'))
        discount.opt = _normalize_percentage(row.get('ОПТ'))
        discount.gd = _normalize_percentage(row.get('ГД'))
        discount.holding = _normalize_percentage(row.get('Холдинг'))
        discount.shareholder = _normalize_percentage(row.get('Акционер'))
        discount.action = _normalize_percentage(row.get('Акция'))
        cadastre_date_val = row.get('Дата кадастра')
        if pd.notna(cadastre_date_val):
            try:
                discount.cadastre_date = pd.to_datetime(cadastre_date_val).date()
            except (ValueError, TypeError):
                discount.cadastre_date = None
        else:
            discount.cadastre_date = None
    db.session.commit()
    return f"Обработано {len(df)} строк. Создано: {created_count}, Обновлено: {updated_count}."


def generate_discount_template_excel():
    from .data_service import get_all_complex_names
    print("[DISCOUNT SERVICE] Генерация шаблона скидок...")
    complex_names = get_all_complex_names()
    headers = ['ЖК', 'Тип недвижимости', 'Тип оплаты', 'Дата кадастра', 'МПП', 'РОП', 'КД', 'ОПТ', 'ГД', 'Холдинг',
               'Акционер', 'Акция']
    data = []
    for name in complex_names:
        for prop_type in PropertyType:
            for payment_method in PaymentMethod:
                row = {'ЖК': name, 'Тип недвижимости': prop_type.value, 'Тип оплаты': payment_method.value,
                       'Дата кадастра': '', 'МПП': 0, 'РОП': 0, 'КД': 0, 'ОПТ': 0, 'ГД': 0, 'Холдинг': 0, 'Акционер': 0,
                       'Акция': 0}
                data.append(row)
    df = pd.DataFrame(data, columns=headers)
    output = io.BytesIO()
    df.to_excel(output, index=False, sheet_name='Шаблон скидок')
    output.seek(0)
    return output


def get_discounts_with_summary():
    """
    Версия 9: Генерирует производные виды оплат "3 транша" и возвращает теги.
    """
    all_sells = EstateSell.query.options(joinedload(EstateSell.house)).all()
    all_discounts = Discount.query.all()

    if not all_discounts: return {}

    discounts_map = {}
    for d in all_discounts:
        discounts_map.setdefault(d.complex_name, []).append(d)

    sells_by_complex = {}
    for s in all_sells:
        if s.house:
            sells_by_complex.setdefault(s.house.complex_name, []).append(s)

    final_data = {}
    valid_statuses = ["Маркетинговый резерв", "Подбор"]
    tag_fields = {'kd': 'КД', 'opt': 'ОПТ', 'gd': 'ГД', 'holding': 'Холдинг', 'shareholder': 'Акционер'}

    all_complex_names = sorted(list(discounts_map.keys()))

    for complex_name in all_complex_names:
        summary = {"sum_100_payment": 0, "sum_mortgage": 0, "months_to_cadastre": None, "avg_remainder_price_sqm": 0,
                   "available_tags": set(), "max_action_discount": 0.0}

        discounts_in_complex = discounts_map.get(complex_name, [])
        details_with_derived = {}

        # Обрабатываем существующие скидки и генерируем производные
        for discount in discounts_in_complex:
            prop_type_val = discount.property_type.value
            details_with_derived.setdefault(prop_type_val, []).append(discount)

            # Для квартир генерируем "3 транша"
            if discount.property_type == PropertyType.FLAT:
                derived_discount = None
                if discount.payment_method == PaymentMethod.FULL_PAYMENT:
                    derived_discount = copy.copy(discount)
                    derived_discount.payment_method = PaymentMethod.TRANCHE_100
                    derived_discount.kd = 0  # Обнуляем КД
                elif discount.payment_method == PaymentMethod.MORTGAGE:
                    derived_discount = copy.copy(discount)
                    derived_discount.payment_method = PaymentMethod.TRANCHE_MORTGAGE
                    derived_discount.kd = 0  # Обнуляем КД

                if derived_discount:
                    details_with_derived[prop_type_val].append(derived_discount)

        # Расчет summary (на основе оригинальных данных)
        base_discount_100 = next((d for d in discounts_in_complex if
                                  d.property_type == PropertyType.FLAT and d.payment_method == PaymentMethod.FULL_PAYMENT),
                                 None)
        base_discount_mortgage = next((d for d in discounts_in_complex if
                                       d.property_type == PropertyType.FLAT and d.payment_method == PaymentMethod.MORTGAGE),
                                      None)

        if base_discount_100:
            summary["sum_100_payment"] = base_discount_100.mpp + base_discount_100.rop
            if base_discount_100.cadastre_date:
                today = date.today()
                if base_discount_100.cadastre_date > today:
                    delta = base_discount_100.cadastre_date - today
                    summary["months_to_cadastre"] = int(delta.days / 30.44)

        if base_discount_mortgage:
            summary["sum_mortgage"] = base_discount_mortgage.mpp + base_discount_mortgage.rop

        # ... (логика расчета средней цены остается прежней)
        total_discount_rate = (
                    base_discount_100.mpp + base_discount_100.rop + base_discount_100.kd) if base_discount_100 else 0
        remainder_prices_per_sqm = []
        for sell in sells_by_complex.get(complex_name, []):
            if (
                    sell.estate_sell_status_name in valid_statuses and sell.estate_sell_category == 'flat' and sell.estate_price and sell.estate_price > 0 and sell.estate_area and sell.estate_area > 0):
                price_after_deduction = sell.estate_price - 3_000_000
                if price_after_deduction > 0:
                    final_price = price_after_deduction * (1 - total_discount_rate)
                    remainder_prices_per_sqm.append(final_price / sell.estate_area)
        if remainder_prices_per_sqm:
            avg_price_per_sqm = sum(remainder_prices_per_sqm) / len(remainder_prices_per_sqm)
            summary["avg_remainder_price_sqm"] = avg_price_per_sqm / 12500

        # Сбор тегов
        for discount in discounts_in_complex:
            if discount.action > summary["max_action_discount"]:
                summary["max_action_discount"] = discount.action
            for field, tag_name in tag_fields.items():
                if getattr(discount, field, 0) > 0:
                    summary["available_tags"].add(tag_name)

        final_data[complex_name] = {"summary": summary, "details": details_with_derived}

    return final_data
