from app.core.extensions import db


class EstateHouse(db.Model):
    __tablename__ = 'estate_houses'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    complex_name = db.Column(db.String(255), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    geo_house = db.Column(db.String(50))

    sells = db.relationship('EstateSell', back_populates='house')


class EstateSell(db.Model):
    __tablename__ = 'estate_sells'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(db.Integer, db.ForeignKey('estate_houses.id'), nullable=False)

    estate_sell_category = db.Column(db.String(100))
    estate_floor = db.Column(db.Integer)
    estate_rooms = db.Column(db.Integer)
    estate_price_m2 = db.Column(db.Float)

    estate_sell_status_name = db.Column(db.String(100), nullable=True)
    estate_price = db.Column(db.Float, nullable=True)

    # --- НОВОЕ ПОЛЕ ---
    estate_area = db.Column(db.Float, nullable=True)  # Площадь объекта

    house = db.relationship('EstateHouse', back_populates='sells')
