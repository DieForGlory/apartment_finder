import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a-very-secret-key'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --- ОБНОВИТЕ ПАРОЛЬ ЗДЕСЬ ---
    SOURCE_MYSQL_URI = (
        f"mysql+pymysql://"
        f"macro_bi_cmp_528:p[8qG^]Qf3v[qr*1@172.16.0.199:9906/macro_bi_cmp_528"
    )
    # --------------------------------

class DevelopmentConfig(Config):
    DEBUG = True
    # Основной базой остается локальная SQLite, здесь ничего не меняем.