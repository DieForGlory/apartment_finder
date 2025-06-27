# app/models/discount_models.py

from app.core.extensions import db
from sqlalchemy import Enum as SQLAlchemyEnum, func
import enum


class PropertyType(enum.Enum):
    FLAT = 'Квартира'
    COMM = 'Коммерческое помещение'
    GARAGE = 'Парковка'
    STORAGEROOM = 'Кладовое помещение'


class PaymentMethod(enum.Enum):
    """
    Оставили только два основных способа оплаты.
    """
    FULL_PAYMENT = '100% оплата'
    MORTGAGE = 'Ипотека'


class DiscountVersion(db.Model):
    """Модель для хранения версий системы скидок."""
    __tablename__ = 'discount_versions'

    id = db.Column(db.Integer, primary_key=True)
    version_number = db.Column(db.Integer, nullable=False, unique=True)
    comment = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    # Поле для хранения JSON с детальными комментариями к изменениям
    changes_summary_json = db.Column(db.Text, nullable=True)

    # Связи с другими моделями
    discounts = db.relationship('Discount', back_populates='version', cascade="all, delete-orphan")
    complex_comments = db.relationship('ComplexComment', back_populates='version', cascade="all, delete-orphan")


class Discount(db.Model):
    __tablename__ = 'discounts'

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('discount_versions.id'), nullable=False, index=True)

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
    action = db.Column(db.Float, default=0.0)
    cadastre_date = db.Column(db.Date, nullable=True)

    version = db.relationship('DiscountVersion', back_populates='discounts')

    __table_args__ = (
        db.UniqueConstraint('version_id', 'complex_name', 'property_type', 'payment_method',
                            name='_version_complex_prop_payment_uc'),
    )


class ComplexComment(db.Model):
    """Модель для хранения комментариев к ЖК в рамках версии."""
    __tablename__ = 'complex_comments'

    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('discount_versions.id'), nullable=False)
    complex_name = db.Column(db.String(255), nullable=False, index=True)
    comment = db.Column(db.Text, nullable=True)

    version = db.relationship('DiscountVersion', back_populates='complex_comments')

    __table_args__ = (
        db.UniqueConstraint('version_id', 'complex_name', name='_version_complex_uc'),
    )