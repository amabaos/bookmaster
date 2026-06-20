import os
from fastapi import Request, HTTPException, status
from fastapi.responses import RedirectResponse

ADMIN_LOGIN = os.getenv("ADMIN_LOGIN", "admin")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")
SESSION_KEY = "authenticated"


def check_auth(request: Request) -> bool:
    return request.session.get(SESSION_KEY) is True


def require_auth(request: Request):
    if not check_auth(request):
        raise HTTPException(status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                            headers={"Location": "/login"})


def login(request: Request, login: str, password: str) -> bool:
    if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        request.session[SESSION_KEY] = True
        return True
    return False


def logout(request: Request):
    request.session.clear()
