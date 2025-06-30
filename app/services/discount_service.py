import json
import copy
from datetime import date
from sqlalchemy.orm import joinedload
from flask import render_template_string
import requests
from ..core.extensions import db
from ..models.discount_models import Discount, DiscountVersion, PropertyType, PaymentMethod, ComplexComment
from ..models.estate_models import EstateSell
from .email_service import send_email
import pandas as pd
import io


def get_current_usd_rate():
    """
    Получает актуальный курс USD к UZS с API Центрального банка Республики Узбекистан.
    Возвращает курс (float) или None в случае ошибки.
    """
    # API ЦБРУ: https://cbu.uz/ru/arkhiv-kursov-valyut/
    # Пример API: https://cbu.uz/oz/arkhiv-kursov-valyut/json/
    # Для получения актуального курса на сегодня, можно использовать:
    # https://cbu.uz/oz/arkhiv-kursov-valyut/json/all/
    # Искать по "Ccy":"USD"

    api_url = "https://cbu.uz/oz/arkhiv-kursov-valyut/json/"
    print(f"\n[DISCOUNT SERVICE] Попытка получить курс USD с API ЦБ: {api_url}")

    try:
        response = requests.get(api_url, timeout=5, verify=False)  # Таймаут 5 секунд
        response.raise_for_status()  # Проверить на HTTP ошибки (4xx, 5xx)
        data = response.json()

        for currency_data in data:
            if currency_data.get("Ccy") == "USD":
                rate = float(currency_data.get("Rate").replace(',', '.'))  # Заменить запятую на точку для float
                print(f"[DISCOUNT SERVICE] ✔️ Получен актуальный курс USD с ЦБ: {rate}")
                return rate

        print("[DISCOUNT SERVICE] ❕ Курс USD не найден в ответе API ЦБ.")
        return None

    except requests.exceptions.RequestException as e:
        print(f"[DISCOUNT SERVICE] ❌ Ошибка при запросе к API ЦБ: {e}")
        return None
    except (json.JSONDecodeError, AttributeError, KeyError, ValueError) as e:
        print(f"[DISCOUNT SERVICE] ❌ Ошибка обработки ответа API ЦБ: {e}")
        return None
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

    # --- НОВОЕ: ОТЛАДОЧНЫЙ ВЫВОД ДАТАФРЕЙМА ---
    print("[DISCOUNT SERVICE] Загруженный DataFrame:")
    print(df.head())  # Выводит первые 5 строк DataFrame
    if df.empty:
        print("[DISCOUNT SERVICE] DataFrame пуст. Возможно, файл некорректен или пуст.")
        return "Ошибка: Файл Excel пуст или не содержит данных."
    # --- КОНЕЦ ОТЛАДОЧНОГО ВЫВОДА ---

    created_count, updated_count = 0, 0

    existing_discounts = {
        (d.complex_name, d.property_type, d.payment_method): d
        for d in Discount.query.filter_by(version_id=version_id).all()
    }

    # --- НОВОЕ: ОТЛАДОЧНЫЙ БЛОК TRY-EXCEPT ДЛЯ КАЖДОЙ СТРОКИ ---
    for index, row in df.iterrows():
        try:
            # --- НОВОЕ: ВЫВОД ТЕКУЩЕЙ СТРОКИ ИЗ EXCEL ---
            print(f"[DISCOUNT SERVICE] Обработка строки {index}: {row.to_dict()}")
            # --- КОНЕЦ ВЫВОДА ---

            # Проверка наличия всех обязательных колонок
            required_columns = ['ЖК', 'Тип недвижимости', 'Тип оплаты']
            for col in required_columns:
                if col not in row:
                    raise KeyError(f"Отсутствует обязательная колонка: '{col}' в строке {index}")

            # Добавим дополнительную проверку на тип данных для property_type и payment_method
            prop_type_val = row['Тип недвижимости']
            payment_method_val = row['Тип оплаты']

            # Проверка, что значения соответствуют Enum
            try:
                property_type_enum = PropertyType(prop_type_val)
            except ValueError:
                raise ValueError(
                    f"Неизвестный 'Тип недвижимости': '{prop_type_val}' в строке {index}. Ожидается: {', '.join([pt.value for pt in PropertyType])}")

            try:
                payment_method_enum = PaymentMethod(payment_method_val)
            except ValueError:
                raise ValueError(
                    f"Неизвестный 'Тип оплаты': '{payment_method_val}' в строке {index}. Ожидается: {', '.join([pm.value for pm in PaymentMethod])}")

            key = (
                row['ЖК'],
                property_type_enum,
                payment_method_enum
            )
            discount = existing_discounts.get(key)

            if not discount:
                discount = Discount(
                    version_id=version_id,
                    complex_name=row['ЖК'],
                    property_type=property_type_enum,
                    payment_method=payment_method_enum
                )
                db.session.add(discount)
                created_count += 1
            else:
                updated_count += 1

            # --- НОВОЕ: ВЫВОД ЗНАЧЕНИЙ ПЕРЕД ПРИСВОЕНИЕМ ---
            print(f"[DISCOUNT SERVICE] Значения скидок для '{row['ЖК']}':")
            print(f"  МПП: {row.get('МПП')}, РОП: {row.get('РОП')}, КД: {row.get('КД')}")
            # --- КОНЕЦ ВЫВОДА ---

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
                    print(
                        f"[DISCOUNT SERVICE] ВНИМАНИЕ: Не удалось разобрать дату кадастра '{cadastre_date_val}' в строке {index}. Устанавливаю None.")
                    discount.cadastre_date = None
            else:
                discount.cadastre_date = None

        except KeyError as ke:
            print(f"[DISCOUNT SERVICE] ❌ ОШИБКА ОБРАБОТКИ СТРОКИ {index} (KeyError): {ke}. Пропускаю строку.")
            # Если это критическая ошибка, можно re-raise или сбросить весь файл.
            # Пока пропускаем, чтобы увидеть другие ошибки.
        except ValueError as ve:
            print(f"[DISCOUNT SERVICE] ❌ ОШИБКА ОБРАБОТКИ СТРОКИ {index} (ValueError): {ve}. Пропускаю строку.")
        except Exception as ex:
            print(
                f"[DISCOUNT SERVICE] ❌ НЕИЗВЕСТНАЯ ОШИБКА ОБРАБОТКИ СТРОКИ {index}: {type(ex).__name__}: {ex}. Пропускаю строку.")

    # --- КОНЕЦ ОТЛАДОЧНОГО БЛОКА ---

    print(f"[DISCOUNT SERVICE] Завершение обработки. Создано: {created_count}, Обновлено: {updated_count}.")
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
    Получает данные для страницы "Система скидок", включая комментарии к ЖК.
    """

    active_version = DiscountVersion.query.filter_by(is_active=True).first()
    if not active_version:
        return {}

    all_discounts = active_version.discounts

    comments = ComplexComment.query.filter_by(version_id=active_version.id).all()
    comments_map = {c.complex_name: c.comment for c in comments}

    if not all_discounts:
        return {}

    discounts_map = {}
    for d in all_discounts:
        discounts_map.setdefault(d.complex_name, []).append(d)

    all_sells = EstateSell.query.options(joinedload(EstateSell.house)).all()
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

        summary["complex_comment"] = comments_map.get(complex_name)

        discounts_in_complex = discounts_map.get(complex_name, [])
        details_by_prop_type = {}

        for discount in discounts_in_complex:
            prop_type_val = discount.property_type.value
            details_by_prop_type.setdefault(prop_type_val, []).append(discount)

        base_discount_100 = next((d for d in discounts_in_complex if
                                  d.property_type == PropertyType.FLAT and d.payment_method == PaymentMethod.FULL_PAYMENT),
                                 None)



        if base_discount_100:
            summary["sum_100_payment"] = (base_discount_100.mpp or 0) + (base_discount_100.rop or 0)
            if base_discount_100.cadastre_date:
                today = date.today()
                if base_discount_100.cadastre_date > today:
                    delta = base_discount_100.cadastre_date - today
                    summary["months_to_cadastre"] = int(delta.days / 30.44)

        base_discount_mortgage = next((d for d in discounts_in_complex if
                                       d.property_type == PropertyType.FLAT and d.payment_method == PaymentMethod.MORTGAGE),
                                      None)


        if base_discount_mortgage:
            summary["sum_mortgage"] = (base_discount_mortgage.mpp or 0) + (base_discount_mortgage.rop or 0)

        total_discount_rate = 0
        if base_discount_100:
            total_discount_rate = (base_discount_100.mpp or 0) + \
                                  (base_discount_100.rop or 0) + \
                                  (base_discount_100.kd or 0) + \
                                  (base_discount_100.action or 0)

        remainder_prices_per_sqm = []
        sells_in_complex = sells_by_complex.get(complex_name, [])

        processed_sells_count = 0
        for sell in sells_in_complex:
            # Проверка условий фильтрации
            is_valid_status = sell.estate_sell_status_name in valid_statuses
            is_flat_category = sell.estate_sell_category == PropertyType.FLAT.value  # Важно: PropertyType.FLAT.value должно быть "Квартира"
            is_valid_price = sell.estate_price and sell.estate_price > 0
            is_valid_area = sell.estate_area and sell.estate_area > 0

            if (is_valid_status and is_flat_category and is_valid_price and is_valid_area):
                price_after_deduction = (sell.estate_price or 0) - 3_000_000
                if price_after_deduction > 0:
                    final_price = price_after_deduction * (1 - total_discount_rate)
                    if sell.estate_area and sell.estate_area > 0:
                        remainder_prices_per_sqm.append(final_price / sell.estate_area)
                        processed_sells_count += 1

        if remainder_prices_per_sqm:
            avg_price_per_sqm = sum(remainder_prices_per_sqm) / len(remainder_prices_per_sqm)
            avg_price_per_sqm_usd = avg_price_per_sqm / 12500.0  # Используем фиксированный курс для отображения
            summary["avg_remainder_price_sqm"] = avg_price_per_sqm_usd
        else:
            summary["avg_remainder_price_sqm"] = 0  # Убедимся, что явно 0, если нет данных

        for discount in discounts_in_complex:
            if discount.action > summary["max_action_discount"]:
                summary["max_action_discount"] = discount.action
            for field, tag_name in tag_fields.items():
                if getattr(discount, field, 0) > 0:
                    summary["available_tags"].add(tag_name)

        final_data[complex_name] = {"summary": summary, "details": details_by_prop_type}
    return final_data


def _generate_version_comparison_summary(old_version, new_version, comments_data=None):
    """Генерирует HTML-отчет о различиях между двумя версиями, включая комментарии."""
    if comments_data is None:
        comments_data = {}

    old_discounts = {
        (d.complex_name, d.property_type.value, d.payment_method.value): d
        for d in old_version.discounts
    }
    new_discounts = {
        (d.complex_name, d.property_type.value, d.payment_method.value): d
        for d in new_version.discounts
    }

    changes = {'added': [], 'removed': [], 'modified': [], 'user_comments': comments_data}

    for key, new_d in new_discounts.items():
        if key not in old_discounts:
            changes['added'].append(f"Добавлена скидка для {key[0]} ({key[1]}, {key[2]})")
            continue

        old_d = old_discounts[key]
        diffs = []

        for field in ['mpp', 'rop', 'kd', 'opt', 'gd', 'holding', 'shareholder', 'action']:
            old_val = getattr(old_d, field)
            new_val = getattr(new_d, field)

            if abs(old_val - new_val) > 1e-9:
                delta = new_val - old_val
                old_percent = old_val * 100
                new_percent = new_val * 100
                delta_percent = abs(delta * 100)

                if delta > 0:
                    verb = "увеличилась на"
                else:
                    verb = "уменьшилась на"

                diff_text = (
                    f"<b>{field.upper()}</b> {verb} {delta_percent:.1f} % "
                    f"(с {old_percent:.1f}% до {new_percent:.1f}%)"
                )
                diffs.append(diff_text)

        if diffs:
            changes['modified'].append(
                f"<strong>{key[0]} ({key[1]}, {key[2]}):</strong><ul>{''.join(f'<li>{d}</li>' for d in diffs)}</ul>")

    for key, old_d in old_discounts.items():
        if key not in new_discounts:
            changes['removed'].append(f"Удалена скидка для {key[0]} ({key[1]}, {key[2]})")

    email_html = render_template_string("""
        <h3>Здравствуйте!</h3>
        <p>В системе ApartmentFinder была активирована новая версия скидок.</p>
        <p>
            <b>Предыдущая активная версия:</b> №{{ old_v.version_number }} (от {{ old_v.created_at.strftime('%Y-%m-%d %H:%M') }})<br>
            <b>Новая активная версия:</b> №{{ new_v.version_number }} (от {{ new_v.created_at.strftime('%Y-%m-%d %H:%M') }})
        </p>
        <hr>
        <h4>Детальное саммари изменений:</h4>

        {% if changes.user_comments %}
            {% for group_data in changes.user_comments.values() %}
                {% if group_data.comment %}
                    <div style="background-color: #f8f9fa; border-left: 4px solid #ffc107; padding: 10px; margin-bottom: 15px;">
                        <p style="margin: 0;"><b>Комментарий к группе '{{ group_data.complex }} ({{ group_data.propType }})':</b></p>
                        <p style="margin: 0;"><i>«{{ group_data.comment }}»</i></p>
                    </div>
                {% endif %}
            {% endfor %}
        {% endif %}

        {% if changes.modified %}
            <h5>Измененные скидки:</h5>
            <div>
                {% for change in changes.modified %}<p style="margin: 5px 0;">{{ change|safe }}</p>{% endfor %}
            </div>
        {% endif %}

        {% if changes.added %}
            <h5>Добавленные скидки:</h5>
            <ul>
                {% for change in changes.added %}<li>{{ change }}</li>{% endfor %}
            </ul>
        {% endif %}

        {% if changes.removed %}
            <h5>Удаленные скидки:</h5>
            <ul>
                {% for change in changes.removed %}<li>{{ change }}</li>{% endfor %}
            </ul>
        {% endif %}

        {% if not (changes.modified or changes.added or changes.removed) %}
            <p>Структурных изменений в скидках не обнаружено.</p>
        {% endif %}
    """, old_v=old_version, new_v=new_version, changes=changes)

    return email_html


def create_blank_version(comment: str):
    """Создает новую, ПУСТУЮ запись о версии скидок БЕЗ КОММИТА."""
    print(f"\n[DISCOUNT SERVICE] 🚀 Создание ПУСТОЙ версии с комментарием: '{comment}'")

    latest_version = DiscountVersion.query.order_by(DiscountVersion.version_number.desc()).first()

    new_version_number = 1
    if latest_version:
        new_version_number = latest_version.version_number + 1

    new_version = DiscountVersion(version_number=new_version_number, comment=comment)
    db.session.add(new_version)

    # !!! УДАЛЕНО: db.session.commit() !!!
    db.session.flush()  # Используем flush, чтобы получить ID для new_version, но не фиксируем транзакцию

    print(f"[DISCOUNT SERVICE] ✔️ Успешно подготовлена пустая версия №{new_version_number}")
    return new_version


def create_new_version(comment: str):
    """Создает новую версию системы скидок, копируя данные из последней существующей."""
    print(f"\n[DISCOUNT SERVICE] 🚀 Создание новой версии с комментарием: '{comment}'")

    latest_version = DiscountVersion.query.order_by(DiscountVersion.version_number.desc()).first()

    new_version_number = 1
    if latest_version:
        new_version_number = latest_version.version_number + 1

    new_version = DiscountVersion(version_number=new_version_number, comment=comment)
    db.session.add(new_version)

    if latest_version:
        discounts_to_copy = Discount.query.filter_by(version_id=latest_version.id).all()
        print(
            f"[DISCOUNT SERVICE] 📝 Найдено {len(discounts_to_copy)} скидок для копирования из версии №{latest_version.version_number}.")

        for old_discount in discounts_to_copy:
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

        # --- НОВОЕ: Копируем комментарии к ЖК ---
        comments_to_copy = ComplexComment.query.filter_by(version_id=latest_version.id).all()
        for old_comment in comments_to_copy:
            new_comment = ComplexComment(
                version=new_version,
                complex_name=old_comment.complex_name,
                comment=old_comment.comment
            )
            db.session.add(new_comment)
        print(f"[DISCOUNT SERVICE] 📝 Скопировано {len(comments_to_copy)} комментариев к ЖК.")

    db.session.commit()
    print(f"[DISCOUNT SERVICE] ✔️ Успешно создана версия №{new_version_number}")
    return new_version


def update_discounts_for_version(version_id: int, form_data: dict, changes_json: str):
    """Обновляет значения скидок по бизнес-ключу и выводит саммари."""
    target_version = DiscountVersion.query.get(version_id)
    if not target_version:
        return "Ошибка: Версия не найдена."

    discounts_map = {
        (d.complex_name, d.property_type.value, d.payment_method.value): d
        for d in target_version.discounts
    }

    updated_fields_count = 0

    for key, field_value in form_data.items():
        if key.startswith('discount-'):
            try:
                data_part = key[len('discount-'):]
                business_key_str, field_name = data_part.rsplit('-', 1)
                complex_name, prop_type, payment_method = business_key_str.split('|')
            except ValueError:
                continue

            discount_to_update = discounts_map.get((complex_name, prop_type, payment_method))

            if discount_to_update:
                try:
                    new_value = float(field_value) / 100.0
                    if abs(getattr(discount_to_update, field_name) - new_value) > 1e-9:
                        setattr(discount_to_update, field_name, new_value)
                        updated_fields_count += 1
                except (ValueError, TypeError):
                    continue

    print(f"\n[DISCOUNT UPDATE] 💾 Сохранение изменений для версии №{target_version.version_number} (ID: {version_id})")
    try:
        changes_data = json.loads(changes_json)
        print("-" * 50)
        for group_key, group_data in changes_data.items():
            print(f"Группа: {group_data['complex']} ({group_data['propType']})")
            print(f"  [COMMENT] 💬: {group_data.get('comment', 'Без комментария')}")
            for mod in group_data.get('modifications', []):
                print(
                    f"    - Поле '{mod['fieldName']}' ({mod['paymentMethod']}): {mod['oldValue']}% → {mod['newValue']}%")
        print("-" * 50)
    except (json.JSONDecodeError, AttributeError):
        print("[DISCOUNT UPDATE] ⚠️ Не удалось разобрать JSON с комментариями.")

    if updated_fields_count > 0:
        db.session.commit()
        print(f"[DISCOUNT UPDATE] ✔️ Изменения успешно сохранены в БД. Затронуто полей: {updated_fields_count}")
        return f"Изменения успешно сохранены."
    else:
        db.session.rollback()
        print("[DISCOUNT UPDATE] ❕ Нет фактических изменений для сохранения в БД.")
        return "Изменений для сохранения не найдено."


def activate_version(version_id: int):
    """Активирует выбранную версию (надежный метод) и возвращает данные для email."""
    print(f"[DISCOUNT SERVICE] 🔄 Активация версии ID: {version_id}...")

    target_version = DiscountVersion.query.get(version_id)
    if not target_version:
        print(f"[DISCOUNT SERVICE] ❌ Не найдена версия с ID: {version_id}")
        return None

    old_active_version = DiscountVersion.query.filter_by(is_active=True).first()

    if old_active_version and old_active_version.id == target_version.id:
        print(f"[DISCOUNT SERVICE] ❕ Версия №{target_version.version_number} уже активна. Действий не требуется.")
        return None

    if old_active_version:
        old_active_version.is_active = False
        print(f"[DISCOUNT SERVICE] Деактивирована старая версия: №{old_active_version.version_number}")

    target_version.is_active = True
    print(f"[DISCOUNT SERVICE] Активирована новая версия: №{target_version.version_number}")

    db.session.commit()
    print(f"[DISCOUNT SERVICE] ✔️ Изменения статусов версий сохранены в БД.")

    email_data = None
    if old_active_version:
        # --- НОВОЕ: Передаем комментарии из JSON в генератор саммари ---
        comments_data = json.loads(target_version.changes_summary_json) if target_version.changes_summary_json else None
        summary_html = _generate_version_comparison_summary(old_active_version, target_version,
                                                            comments_data=comments_data)
        subject = f"ApartmentFinder: Активирована новая версия скидок №{target_version.version_number}"
        email_data = {'subject': subject, 'html_body': summary_html}
    else:
        subject = f"ApartmentFinder: Активирована первая версия скидок №{target_version.version_number}"
        html_body = "Это первая активация в системе."
        email_data = {'subject': subject, 'html_body': html_body}

    # Возвращаем данные для отправки письма, а не отправляем его отсюда
    return email_data