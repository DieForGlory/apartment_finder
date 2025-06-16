from flask_sqlalchemy import SQLAlchemy

# Создаем экземпляр SQLAlchemy.
# Впоследствии мы свяжем его с нашим Flask app через app.init_app()
db = SQLAlchemy()

# Сюда же в будущем можно добавить другие расширения, например:
# from flask_migrate import Migrate
# migrate = Migrate()