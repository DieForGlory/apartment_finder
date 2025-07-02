from app.models.discount_models import CalculatorSettings
from app.core.extensions import db


def get_calculator_settings():
    """
    Получает настройки калькуляторов. Если их нет, создает по умолчанию.
    Использует паттерн "Синглтон", всегда работая с записью id=1.
    """
    settings = CalculatorSettings.query.get(1)
    if not settings:
        settings = CalculatorSettings(id=1)
        db.session.add(settings)
        db.session.commit()
    return settings


def update_calculator_settings(form_data):
    """Обновляет настройки калькуляторов из данных формы."""
    settings = get_calculator_settings()

    settings.standard_installment_whitelist = form_data.get('standard_installment_whitelist', '')
    settings.dp_installment_whitelist = form_data.get('dp_installment_whitelist', '')
    settings.dp_installment_max_term = int(form_data.get('dp_installment_max_term', 6))
    settings.time_value_rate_annual = float(form_data.get('time_value_rate_annual', 16.5))

    db.session.commit()