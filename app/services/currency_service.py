# app/services/currency_service.py

import requests
from datetime import datetime
from app.core.extensions import db
from app.models.finance_models import CurrencySettings
from flask import current_app
# API Центрального Банка Узбекистана для курса доллара
CBU_API_URL = "https://cbu.uz/ru/arkhiv-kursov-valyut/json/USD/"


def _get_settings():
    """Вспомогательная функция для получения единственной строки настроек."""
    settings = db.session.get(CurrencySettings, 1) # Используем get() вместо first()
    if not settings:
        settings = CurrencySettings(id=1) # Явно указываем ID при создании
        db.session.add(settings)
        # Установим начальные значения при первом создании
        settings.manual_rate = 13050.0
        settings.update_effective_rate()
        db.session.commit()
    return settings


def _update_cbu_rate_logic():
    """Основная логика обновления, вынесенная в отдельную функцию."""
    try:
        response = requests.get(CBU_API_URL, timeout=10, verify=False)
        response.raise_for_status()
        data = response.json()

        rate_str = data[0]['Rate']
        rate_float = float(rate_str)

        settings = _get_settings()
        settings.cbu_rate = rate_float
        settings.cbu_last_updated = datetime.utcnow()

        if settings.rate_source == 'cbu':
            settings.update_effective_rate()

        db.session.commit()
        print(f"Successfully updated CBU rate to: {rate_float}")
        return True
    except requests.RequestException as e:
        print(f"Error fetching CBU rate: {e}")
        return False


def fetch_and_update_cbu_rate(app):
    """Публичная функция, которую вызывает планировщик. Принимает экземпляр приложения."""
    # Убираем создание временного приложения и используем переданный app
    with app.app_context():
        _update_cbu_rate_logic()


def set_rate_source(source: str):
    """Устанавливает источник курса ('cbu' или 'manual')."""
    if source not in ['cbu', 'manual']:
        raise ValueError("Source must be 'cbu' or 'manual'")

    settings = _get_settings()
    settings.rate_source = source
    settings.update_effective_rate()  # Обновляем актуальный курс
    db.session.commit()


def set_manual_rate(rate: float):
    """Устанавливает курс вручную."""
    if rate <= 0:
        raise ValueError("Rate must be positive")

    settings = _get_settings()
    settings.manual_rate = rate
    print(f"DEBUG (currency_service): Ручной курс в базе данных обновлен на: {rate}") # <-- ОТЛАДКА

    # Если активный источник - ручной, обновляем и актуальный курс
    if settings.rate_source == 'manual':
        settings.update_effective_rate()
        print(f"DEBUG (currency_service): Источник 'ручной', effective_rate обновлен на: {settings.effective_rate}") # <-- ОТЛАДКА


    db.session.commit()


def get_current_effective_rate():
    """ЕДИНАЯ функция для получения актуального курса для всех расчетов."""
    settings = _get_settings()
    # v-- ОТЛАДКА --v
    print(f"DEBUG (currency_service): Запрошен effective_rate. Источник: '{settings.rate_source}', Значение: {settings.effective_rate}")
    # ^-- ОТЛАДКА --^
    return settings.effective_rate