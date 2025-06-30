from functools import wraps
from flask import abort
from flask_login import current_user

def role_required(*roles):
    """
    Декоратор для ограничения доступа на основе ролей.
    Пример: @role_required('ADMIN', 'MANAGER')
    """
    def wrapper(fn):
        @wraps(fn)
        def decorated_view(*args, **kwargs):
            if not current_user.is_authenticated:
                # Flask-Login сам перенаправит на страницу входа
                return abort(401)
            if current_user.role.name not in roles:
                # Если роль не подходит, выдаем ошибку "Доступ запрещен"
                abort(403)
            return fn(*args, **kwargs)
        return decorated_view
    return wrapper