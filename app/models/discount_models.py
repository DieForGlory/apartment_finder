from app.core.extensions import db
from sqlalchemy import Enum as SQLAlchemyEnum
import enum

class PropertyType(enum.Enum):
    FLAT = 'flat'
    COMM = 'comm'
    GARAGE = 'garage'
    STORAGEROOM = 'storageroom'

class PaymentMethod(enum.Enum):
    FULL_PAYMENT = '100% оплата'
    MORTGAGE = 'Ипотека'
    # --- НОВЫЕ ТИПЫ ОПЛАТ ---
    TRANCHE_100 = '3 транша - 100% оплата'
    TRANCHE_MORTGAGE = '3 транша - ипотека'

class Discount(db.Model):
    __tablename__ = 'discounts'

    id = db.Column(db.Integer, primary_key=True)
    complex_name = db.Column(db.String(255), nullable=False, index=True)
    property_type = db.Column(SQLAlchemyEnum(PropertyType), nullable=False)
    payment_method = db.Column(SQLAlchemyEnum(PaymentMethod), nullable=False)

    # Колонки для каждой скидки.
    mpp = db.Column(db.Float, default=0.0)
    rop = db.Column(db.Float, default=0.0)
    kd = db.Column(db.Float, default=0.0)
    opt = db.Column(db.Float, default=0.0)
    gd = db.Column(db.Float, default=0.0)
    holding = db.Column(db.Float, default=0.0)
    shareholder = db.Column(db.Float, default=0.0)
    action = db.Column(db.Float, default=0.0) # <-- НОВОЕ ПОЛЕ "АКЦИЯ"
    cadastre_date = db.Column(db.Date, nullable=True)
    __table_args__ = (
        db.UniqueConstraint('complex_name', 'property_type', 'payment_method', name='_complex_prop_payment_uc'),
    )