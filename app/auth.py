from __future__ import annotations

import hmac
from fastapi import Request
from fastapi.responses import RedirectResponse
from .settings import settings

SESSION_KEY = "pt_user"

def auth_config_ok() -> bool:
    if not settings.auth_enabled:
        return True
    return bool(settings.admin_password) and bool(settings.session_secret)

def is_logged_in(request: Request) -> bool:
    if not settings.auth_enabled:
        return True
    return bool(request.session.get(SESSION_KEY))

def require_login(request: Request):
    if not settings.auth_enabled:
        return
    if not is_logged_in(request):
        # raise RedirectResponse is not allowed; dependency can return response via exception
        return RedirectResponse(url="/login", status_code=303)

def try_login(password: str) -> bool:
    if not settings.auth_enabled:
        return True
    return hmac.compare_digest(password or "", settings.admin_password or "")
