from app.core.extensions import db


class FinanceOperation(db.Model):
    __tablename__ = 'finances'

    id = db.Column(db.Integer, primary_key=True)
    estate_sell_id = db.Column(db.Integer, db.ForeignKey('estate_sells.id'), nullable=False)
    summa = db.Column(db.Float)
    status_name = db.Column(db.String(100))  # "Проведено"
    date_added = db.Column(db.Date)

    # Связь для получения информации об объекте
    sell = db.relationship('EstateSell')