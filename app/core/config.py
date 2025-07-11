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

    # --- НОВЫЕ НАСТРОЙКИ ДЛЯ EMAIL ---
    MAIL_SERVER = os.environ.get('EMAIL_SERVER') or 'mail.gh.uz'
    MAIL_PORT = int(os.environ.get('EMAIL_SERVER_PORT') or 587)
    MAIL_USE_TLS = True  # Используем TLS для порта 587
    MAIL_USERNAME = os.environ.get('SEND_FROM_EMAIL') or 'robot@gh.uz'
    MAIL_PASSWORD = os.environ.get('SEND_FROM_EMAIL_PASSWORD') or 'ABwHRMp1'

    # !!! ЗАМЕНИТЕ НА РЕАЛЬНЫЙ АДРЕС ПОЛУЧАТЕЛЯ !!!
    MAIL_RECIPIENTS = ['d.plakhotnyi@gh.uz']
    USD_TO_UZS_RATE = 13050.0


class DevelopmentConfig(Config):
    DEBUG = True
    # Основной базой остается локальная SQLite, здесь ничего не меняем.