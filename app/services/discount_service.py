from datetime import date
from sqlalchemy.orm import joinedload
from ..core.extensions import db
from ..models.discount_models import Discount, PropertyType, PaymentMethod
from ..models.estate_models import EstateSell
import pandas as pd
import io
import copy
from ..models.discount_models import Discount, DiscountVersion, PropertyType, PaymentMethod


# --- Вспомогательные функции (process_discounts_from_excel, и т.д.) остаются без изменений ---
def create_new_version(comment: str):
    """Создает новую версию системы скидок, копируя данные из последней существующей."""
    print(f"\n[DISCOUNT SERVICE] 🚀 Создание новой версии с комментарием: '{comment}'")

    latest_version = DiscountVersion.query.order_by(DiscountVersion.version_number.desc()).first()

    new_version_number = 1
    if latest_version:
        new_version_number = latest_version.version_number + 1

    # Создаем новую запись о версии
    new_version = DiscountVersion(version_number=new_version_number, comment=comment)
    db.session.add(new_version)

    # Если есть предыдущая версия, копируем все скидки из нее
    if latest_version:
        for old_discount in latest_version.discounts:
            new_discount = Discount(
                version=new_version,
                complex_name=old_discount.complex_name,
                property_type=old_discount.property_type,
                payment_method=old_discount.payment_method,
                mpp=old_discount.mpp,
                rop=old_discount.rop,
                kd=old_discount.kd,
                opt=old_discount.opt,
                gd=old_discount.gd,
                holding=old_discount.holding,
                shareholder=old_discount.shareholder,
                action=old_discount.action,
                cadastre_date=old_discount.cadastre_date
            )
            db.session.add(new_discount)

    db.session.commit()
    print(f"[DISCOUNT SERVICE] ✔️ Успешно создана версия №{new_version_number}")
    return new_version

def activate_version(version_id: int):
    """Активирует выбранную версию, делая все остальные неактивными."""
    print(f"[DISCOUNT SERVICE] 🔄 Активация версии ID: {version_id}...")
    # Сбрасываем флаг у всех версий
    DiscountVersion.query.update({DiscountVersion.is_active: False})
    # Устанавливаем флаг для нужной версии
    target_version = DiscountVersion.query.get(version_id)
    if target_version:
        target_version.is_active = True
        db.session.commit()
        print(f"[DISCOUNT SERVICE] ✔️ Версия №{target_version.version_number} (ID: {version_id}) теперь активна.")
    else:
        print(f"[DISCOUNT SERVICE] ❌ Не найдена версия с ID: {version_id}")


def update_discounts_for_version(version_id: int, form_data: dict, comment: str):
    """Обновляет значения скидок для конкретной версии и выводит саммари в консоль."""
    target_version = DiscountVersion.query.get(version_id)
    if not target_version:
        return "Ошибка: Версия не найдена."

    changes_summary = []

    parsed_data = {}
    for key, value in form_data.items():
        if key.startswith('discount-'):
            parts = key.split('-')
            discount_id = int(parts[1])
            field_name = parts[2]
            parsed_data.setdefault(discount_id, {})[field_name] = value

    for discount_id, fields in parsed_data.items():
        discount = Discount.query.get(discount_id)
        if not discount or discount.version_id != target_version.id:
            continue

        log_prefix = f"  - {discount.complex_name} | {discount.property_type.value} | {discount.payment_method.value}:"

        for field, new_value_str in fields.items():
            try:
                new_value = float(new_value_str) / 100.0
                old_value = getattr(discount, field)

                if abs(old_value - new_value) > 1e-9:  # Сравнение для float
                    changes_summary.append(
                        f"{log_prefix} поле '{field.upper()}' изменено с {old_value * 100:.1f}% на {new_value * 100:.1f}%")
                    setattr(discount, field, new_value)
            except (ValueError, TypeError):
                continue

    if changes_summary:
        print(
            f"\n[DISCOUNT UPDATE] 💾 Сохранение изменений для версии №{target_version.version_number} (ID: {version_id})")
        # --- ВЫВОДИМ КОММЕНТАРИЙ ---
        print(f"[COMMENT] 💬: {comment}")
        for change in changes_summary:
            print(change)
        db.session.commit()
        print("[DISCOUNT UPDATE] ✔️ Изменения успешно сохранены в БД.")
        return f"Сохранено {len(changes_summary)} изменений."
    else:
        print(f"\n[DISCOUNT UPDATE] ❕ Нет изменений для сохранения в версии №{target_version.version_number}.")
        return "Изменений для сохранения не найдено."

def _normalize_percentage(value):
    try:
        num_value = float(value)
        if num_value > 1.0: return num_value / 100.0
        return num_value
    except (ValueError, TypeError):
        return 0.0


def process_discounts_from_excel(file_path: str, version_id: int):
    """
    Обрабатывает Excel-файл и создает/обновляет скидки для УКАЗАННОЙ ВЕРСИИ.
    """
    print(f"\n[DISCOUNT SERVICE] Начало обработки файла: {file_path} для версии ID: {version_id}")
    df = pd.read_excel(file_path)
    created_count, updated_count = 0, 0

    # Получаем все скидки для данной версии один раз, чтобы избежать лишних запросов к БД
    existing_discounts = {
        (d.complex_name, d.property_type, d.payment_method): d
        for d in Discount.query.filter_by(version_id=version_id).all()
    }

    for index, row in df.iterrows():
        # Формируем ключ для поиска в словаре
        key = (
            row['ЖК'],
            PropertyType(row['Тип недвижимости']),
            PaymentMethod(row['Тип оплаты'])
        )

        discount = existing_discounts.get(key)

        if not discount:
            discount = Discount(
                version_id=version_id,  # <-- ПРИВЯЗКА К ВЕРСИИ
                complex_name=row['ЖК'],
                property_type=PropertyType(row['Тип недвижимости']),
                payment_method=PaymentMethod(row['Тип оплаты'])
            )
            db.session.add(discount)
            created_count += 1
        else:
            updated_count += 1

        # ... (остальная часть функции с присвоением mpp, rop и т.д. остается БЕЗ ИЗМЕНЕНИЙ) ...
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

    # Не коммитим здесь, позволяем вызывающей функции управлять транзакцией
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
    Версия 10: РАБОТАЕТ С АКТИВНОЙ ВЕРСИЕЙ СКИДОК.
    Генерирует производные виды оплат и возвращает теги.
    """
    # 1. Находим активную версию
    active_version = DiscountVersion.query.filter_by(is_active=True).first()
    if not active_version:
        return {}  # Если нет активной версии, возвращаем пустые данные

    # 2. Получаем скидки ТОЛЬКО для активной версии
    all_discounts = active_version.discounts
    # ... остальная часть функции get_discounts_with_summary остается такой же, как в discount_service.py

    all_sells = EstateSell.query.options(joinedload(EstateSell.house)).all()

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

        for discount in discounts_in_complex:
            prop_type_val = discount.property_type.value
            details_with_derived.setdefault(prop_type_val, []).append(discount)

            if discount.property_type == PropertyType.FLAT:
                derived_discount = None
                if discount.payment_method == PaymentMethod.FULL_PAYMENT:
                    derived_discount = copy.copy(discount)
                    derived_discount.payment_method = PaymentMethod.TRANCHE_100
                    derived_discount.kd = 0
                elif discount.payment_method == PaymentMethod.MORTGAGE:
                    derived_discount = copy.copy(discount)
                    derived_discount.payment_method = PaymentMethod.TRANCHE_MORTGAGE
                    derived_discount.kd = 0

                if derived_discount:
                    details_with_derived[prop_type_val].append(derived_discount)

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

        for discount in discounts_in_complex:
            if discount.action > summary["max_action_discount"]:
                summary["max_action_discount"] = discount.action
            for field, tag_name in tag_fields.items():
                if getattr(discount, field, 0) > 0:
                    summary["available_tags"].add(tag_name)

        final_data[complex_name] = {"summary": summary, "details": details_with_derived}

    return final_data
