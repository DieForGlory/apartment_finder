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
    __bind_key__ = 'discounts'
    id = db.Column(db.Integer, primary_key=True)
    version_number = db.Column(db.Integer, nullable=False, unique=True)
    comment = db.Column(db.Text, nullable=True)
    is_active = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())
    was_ever_activated = db.Column(db.Boolean, default=False, nullable=False)
    # Поле для хранения JSON с детальными комментариями к изменениям
    changes_summary_json = db.Column(db.Text, nullable=True)
    summary_sent_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Связи с другими моделями
    discounts = db.relationship('Discount', back_populates='version', cascade="all, delete-orphan")
    complex_comments = db.relationship('ComplexComment', back_populates='version', cascade="all, delete-orphan")

class SalesPlan(db.Model):
    """Модель для хранения плановых показателей по продажам."""
    __tablename__ = 'sales_plans'
    __bind_key__ = 'discounts' # Храним планы в той же БД, что и скидки

    id = db.Column(db.Integer, primary_key=True)
    complex_name = db.Column(db.String(255), nullable=False, index=True)
    property_type = db.Column(db.String(100), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    plan_units = db.Column(db.Integer, nullable=False, default=0) # План в штуках
    plan_volume = db.Column(db.Float, nullable=False, default=0.0)
    plan_income = db.Column(db.Float, nullable=False, default=0.0)  # План по поступлениям в UZS
    __table_args__ = (
        db.UniqueConstraint('year', 'month', 'complex_name', 'property_type', name='_plan_period_complex_prop_uc'),
    )

class Discount(db.Model):
    __tablename__ = 'discounts'
    __bind_key__ = 'discounts'
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
    __bind_key__ = 'discounts'
    id = db.Column(db.Integer, primary_key=True)
    version_id = db.Column(db.Integer, db.ForeignKey('discount_versions.id'), nullable=False)
    complex_name = db.Column(db.String(255), nullable=False, index=True)
    comment = db.Column(db.Text, nullable=True)

    version = db.relationship('DiscountVersion', back_populates='complex_comments')

    __table_args__ = (
        db.UniqueConstraint('version_id', 'complex_name', name='_version_complex_uc'),
    )


class CalculatorSettings(db.Model):
    """Модель для хранения глобальных настроек калькуляторов."""
    __tablename__ = 'calculator_settings'
    __bind_key__ = 'discounts'

    id = db.Column(db.Integer, primary_key=True)
    # Списки ID квартир, для которых доступен калькулятор (через запятую)
    standard_installment_whitelist = db.Column(db.Text, nullable=True)
    dp_installment_whitelist = db.Column(db.Text, nullable=True)

    # Максимальный срок для рассрочки на ПВ
    dp_installment_max_term = db.Column(db.Integer, default=6)

    # Годовая ставка для расчета коэффициента "денег во времени"
    time_value_rate_annual = db.Column(db.Float, default=16.5)
    standard_installment_min_dp_percent = db.Column(db.Float, default=15.0)


class ManagerSalesPlan(db.Model):
    """Модель для хранения индивидуальных планов продаж по менеджерам."""
    __tablename__ = 'manager_sales_plans'

    id = db.Column(db.Integer, primary_key=True)
    # Внешний ключ к таблице sales_managers
    manager_id = db.Column(db.Integer, db.ForeignKey('sales_managers.id'), nullable=False, index=True)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    plan_volume = db.Column(db.Float, nullable=False, default=0.0)  # План по контрактации (UZS)
    plan_income = db.Column(db.Float, nullable=False, default=0.0)  # План по поступлениям (UZS)

    # Связь для удобного доступа к данным менеджера
    manager = db.relationship('app.models.user_models.SalesManager')

    __table_args__ = (
        db.UniqueConstraint('manager_id', 'year', 'month', name='_manager_plan_period_uc'),
    )
