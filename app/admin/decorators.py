from functools import wraps
from flask import abort
from flask_login import login_required, current_user


def admin_required(f):
    """Restrict a route to admin users only. Returns 403 for everyone else."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def seller_required(f):
    """Restrict a route to sellers and admins. Returns 403 for buyers."""
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if not current_user.is_seller:
            abort(403)
        return f(*args, **kwargs)
    return decorated