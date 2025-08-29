from datetime import datetime
from app.core.extensions import db

class ZeroMortgageMatrix(db.Model):
    __tablename__ = 'zero_mortgage_matrix'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    data = db.Column(db.JSON, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ZeroMortgageMatrix {self.name}>'
class FinanceOperation(db.Model):
    __tablename__ = 'finances'

    id = db.Column(db.Integer, primary_key=True)
    estate_sell_id = db.Column(db.Integer, db.ForeignKey('estate_sells.id'), nullable=False)
    summa = db.Column(db.Float)
    status_name = db.Column(db.String(100))
    payment_type = db.Column(db.String(100), name='types_name')
    date_added = db.Column(db.Date)
    date_to = db.Column(db.Date, nullable=True)
    # <-- ИЗМЕНЕНИЕ ЗДЕСЬ: Указываем правильное имя колонки из MySQL
    manager_id = db.Column(db.Integer, name='respons_manager_id')
    data_hash = db.Column(db.String(64), index=True, nullable=True)
    sell = db.relationship('EstateSell')

class CurrencySettings(db.Model):
    __tablename__ = 'currency_settings'
    id = db.Column(db.Integer, primary_key=True)
    # Какой источник используется: 'cbu' или 'manual'
    rate_source = db.Column(db.String(10), default='cbu', nullable=False)
    # Последний полученный курс от ЦБ
    cbu_rate = db.Column(db.Float, default=0.0)
    # Курс, установленный вручную
    manual_rate = db.Column(db.Float, default=0.0)
    # Актуальный курс, который используется во всех расчетах
    effective_rate = db.Column(db.Float, default=0.0)
    # Когда последний раз обновлялся курс ЦБ
    cbu_last_updated = db.Column(db.DateTime)

    # Метод для удобного обновления актуального курса
    def update_effective_rate(self):
        if self.rate_source == 'cbu':
            self.effective_rate = self.cbu_rate
        else:
            # ИСПРАВЛЕНИЕ: Устанавливаем ручной курс, а не курс ЦБ
            self.effective_rate = self.manual_rate