from functools import wraps

from flask import session, redirect, url_for, flash


def admin_required(view):
    """Protege una vista exigiendo sesión de administrador activa."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            flash("Inicia sesión como administrador.", "info")
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)

    return wrapped
