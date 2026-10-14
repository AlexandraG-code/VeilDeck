"""Cookie сессии и CSRF: единые имена и атрибуты (SR-04, SR-05, T-04)."""

from fastapi import Response

SID_COOKIE = "__Host-sid"
CSRF_COOKIE = "__Host-csrf"


def set_session_cookies(response: Response, sid: str, csrf: str) -> None:
    """Ставит __Host-sid (HttpOnly) и __Host-csrf (читается SPA для double-submit); Secure, SameSite=Strict, Path=/."""
    response.set_cookie(SID_COOKIE, sid, secure=True, httponly=True, samesite="strict", path="/")
    set_csrf_cookie(response, csrf)


def set_csrf_cookie(response: Response, csrf: str) -> None:
    """Ставит только __Host-csrf (анонимный токен до входа)."""
    response.set_cookie(CSRF_COOKIE, csrf, secure=True, httponly=False, samesite="strict", path="/")


def clear_session_cookies(response: Response) -> None:
    """Затирает обе cookie теми же атрибутами (иначе браузер не удалит __Host-)."""
    response.delete_cookie(SID_COOKIE, secure=True, httponly=True, samesite="strict", path="/")
    response.delete_cookie(CSRF_COOKIE, secure=True, httponly=False, samesite="strict", path="/")
