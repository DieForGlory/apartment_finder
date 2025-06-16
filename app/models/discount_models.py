from app.core.extensions import db
from sqlalchemy import Enum as SQLAlchemyEnum, func
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

    # --- НОВОЕ ПОЛЕ ДЛЯ СВЯЗИ С ВЕРСИЕЙ ---
    version_id = db.Column(db.Integer, db.ForeignKey('discount_versions.id'), nullable=False, index=True)

    complex_name = db.Column(db.String(255), nullable=False, index=True)
    property_type = db.Column(SQLAlchemyEnum(PropertyType), nullable=False)
    payment_method = db.Column(SQLAlchemyEnum(PaymentMethod), nullable=False)

    # ... (колонки для скидок mpp, rop, и т.д. остаются без изменений) ...
    mpp = db.Column(db.Float, default=0.0)
    rop = db.Column(db.Float, default=0.0)
    kd = db.Column(db.Float, default=0.0)
    opt = db.Column(db.Float, default=0.0)
    gd = db.Column(db.Float, default=0.0)
    holding = db.Column(db.Float, default=0.0)
    shareholder = db.Column(db.Float, default=0.0)
    action = db.Column(db.Float, default=0.0)
    cadastre_date = db.Column(db.Date, nullable=True)

    version = db.relationship('DiscountVersion', back_populates='discounts')

    __table_args__ = (
        # Уникальность теперь должна учитывать и версию
        db.UniqueConstraint('version_id', 'complex_name', 'property_type', 'payment_method',
                            name='_version_complex_prop_payment_uc'),
    )

class DiscountVersion(db.Model):
    """Модель для хранения версий системы скидок."""
    __tablename__ = 'discount_versions'

    id = db.Column(db.Integer, primary_key=True)
    # Номер версии для отображения пользователю
    version_number = db.Column(db.Integer, nullable=False, unique=True)
    # Комментарий, описывающий изменения в этой версии
    comment = db.Column(db.Text, nullable=True)
    # Флаг, указывающий, является ли эта версия активной (используемой в расчетах)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # Связь с записями скидок этой версии
    discounts = db.relationship('Discount', back_populates='version', cascade="all, delete-orphan")