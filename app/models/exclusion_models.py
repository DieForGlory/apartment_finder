# app/models/exclusion_models.py

from app.core.extensions import db
from sqlalchemy import func

class ExcludedSell(db.Model):
    __tablename__ = 'excluded_sells'
    __table_args__ = {'extend_existing': True} # Позволяет переопределять таблицу, если она уже определена

    id = db.Column(db.Integer, primary_key=True)
    sell_id = db.Column(db.Integer, nullable=False, unique=True, index=True) # ID исключаемой квартиры
    comment = db.Column(db.String(500), nullable=True) # Причина исключения
    created_at = db.Column(db.DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<ExcludedSell(sell_id={self.sell_id}, comment='{self.comment}')>"