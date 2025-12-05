# core/middleware.py
from django.shortcuts import redirect
from django.urls import reverse
from django.conf import settings
from django.utils.deprecation import MiddlewareMixin

class RoleRequiredMiddleware(MiddlewareMixin):
    """
    Simple middleware that blocks access to path prefixes unless the user has
    one of the allowed roles.

    Configure in settings.py with:
    ROLE_REQUIRED_PATHS = {
        "/admin-only/": ["admin"],
        "/reception/": ["reception", "admin"],
        "/doctor/": ["doctor", "admin"],
    }

    Middleware checks the request.path startswith each key; if matched and
    user isn't authenticated or doesn't have an allowed role -> redirect to login
    (or show forbidden URL).
    """
    def process_request(self, request):
        # Nothing to do if no mapping configured
        mapping = getattr(settings, "ROLE_REQUIRED_PATHS", None)
        if not mapping:
            return None

        path = request.path
        # Find the longest matching prefix (so more specific wins)
        matched_prefix = None
        for prefix in mapping:
            if path.startswith(prefix):
                if matched_prefix is None or len(prefix) > len(matched_prefix):
                    matched_prefix = prefix

        if not matched_prefix:
            return None

        allowed_roles = mapping.get(matched_prefix) or []

        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            # not logged in -> send to login
            return redirect(f"{reverse('login')}?next={request.path}")

        # allow superuser/staff regardless
        if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
            return None

        user_role = (getattr(user, "role", "") or "").lower()
        if user_role in [r.lower() for r in allowed_roles]:
            return None

        # not allowed -> simple forbidden page or redirect
        # You can change to HttpResponseForbidden if you prefer 403.
        return redirect("dashboard")




