# core/decorators.py

from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse


# -------------------------
# ROLE CHECKING HELPERS
# -------------------------

def _get_role(user):
    if not getattr(user, "is_authenticated", False):
        return ""
    raw = getattr(user, "role", "") or ""
    s = str(raw).strip()
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        s = s[1:-1]
    return s.strip().lower()


def is_admin(user):
    """
    Check ONLY role='admin'. We REMOVED is_staff / is_superuser checks
    because the user said they do NOT want those to determine admin.
    """
    return _get_role(user) in ("admin", "administrator")


def is_doctor(user):
    return _get_role(user) in ("doctor", "dr")


def is_receptionist(user):
    return _get_role(user) in ( "receptionist", "frontdesk")


# -------------------------
# DECORATOR FACTORY
# -------------------------

def _role_required(check_func, login_url="login"):
    """Internal reusable decorator creator."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not getattr(request.user, "is_authenticated", False):
                return redirect(f"{reverse(login_url)}?next={request.path}")

            if not check_func(request.user):
                return HttpResponseForbidden("Permission denied.")
            return view_func(request, *args, **kwargs)
        return wrapped
    return decorator


# -------------------------
# PUBLIC DECORATORS
# -------------------------

def admin_required(view_func=None, login_url="login"):
    if view_func:
        return _role_required(is_admin, login_url)(view_func)
    return _role_required(is_admin, login_url)


def doctor_required(view_func=None, login_url="login"):
    if view_func:
        return _role_required(is_doctor, login_url)(view_func)
    return _role_required(is_doctor, login_url)


def receptionist_required(view_func=None, login_url="login"):
    if view_func:
        return _role_required(is_receptionist, login_url)(view_func)
    return _role_required(is_receptionist, login_url)


def doctor_or_receptionist_required(view_func=None, login_url="login"):
    def check(user):
        return is_doctor(user) or is_receptionist(user)

    if view_func:
        return _role_required(check, login_url)(view_func)
    return _role_required(check, login_url)


def receptionist_or_admin_required(view_func=None, login_url="login"):
    def check(user):
        return is_receptionist(user) or is_admin(user)

    if view_func:
        return _role_required(check, login_url)(view_func)
    return _role_required(check, login_url)
