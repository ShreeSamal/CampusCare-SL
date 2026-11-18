"""Login session (tokens + current user).

Access token: memory only. Refresh token (+ a copy of the basic user info): persisted with
ft.SharedPreferences under the "campuscare." prefix, so the user stays logged in across restarts.
Storage is shared by all Flet apps on desktop and is not encrypted - never store passwords.

  restore(page)   startup: stored refresh token -> POST /auth/refresh -> session (new tokens are re-saved)
                    * token rejected by the server -> forget it, show login
                    * no network -> keep the stored token (next launch retries), show login
  set_session()   updates memory and saves the refresh token (Supabase rotates it on every refresh)
  clear()         forgets memory + stored values
"""
import json

import config

_state = {"access": None, "refresh": None, "user": None}
_page = None          # set by restore(); needed to schedule the async storage writes

KEY_REFRESH = "campuscare.refresh"
KEY_USER = "campuscare.user"


def _prefs():
    import flet as ft

    return ft.SharedPreferences()


async def _save() -> None:
    try:
        prefs = _prefs()
        await prefs.set(KEY_REFRESH, _state["refresh"])
        await prefs.set(KEY_USER, json.dumps(_state["user"] or {}))
    except Exception as exc:  # noqa: BLE001 - storage problems must never break login
        print("Could not save the session:", repr(exc))


async def _forget() -> None:
    try:
        prefs = _prefs()
        await prefs.remove(KEY_REFRESH)
        await prefs.remove(KEY_USER)
    except Exception as exc:  # noqa: BLE001
        print("Could not remove the stored session:", repr(exc))


def _schedule(coro_fn) -> None:
    if _page is not None:
        try:
            _page.run_task(coro_fn)
        except Exception as exc:  # noqa: BLE001
            print("Could not schedule session storage:", repr(exc))


async def restore(page) -> None:
    """Called once at startup, before the first screen is chosen."""
    global _page
    _page = page
    try:
        token = await _prefs().get(KEY_REFRESH)
    except Exception as exc:  # noqa: BLE001
        print("Could not read the stored session:", repr(exc))
        return
    if not token or not isinstance(token, str):
        return

    from core.api_client import ApiError, NetworkError
    from services import auth_service

    try:
        fresh = await auth_service.refresh(token)
    except NetworkError:
        return                          # offline: keep the token, the user can log in or retry later
    except ApiError as exc:
        if exc.status_code in (400, 401, 403):
            await _forget()
        return
    except Exception as exc:  # noqa: BLE001
        print("Session restore failed:", repr(exc))
        return

    if fresh.get("access") and fresh.get("user"):
        set_session(fresh["access"], fresh["refresh"] or token, fresh["user"])


def set_session(access: str, refresh: str, user: dict) -> None:
    _state.update(access=access, refresh=refresh, user=user)
    if access != "dev" and refresh:
        _schedule(_save)


def update_user(fields: dict) -> None:
    """Merge fresh profile fields (e.g. from GET /auth/me) into the logged-in user."""
    if _state["user"] is not None:
        _state["user"] = {**_state["user"], **{k: v for k, v in fields.items() if v is not None}}
        if not is_dev_session():
            _schedule(_save)


def update_tokens(access: str, refresh: str | None) -> None:
    """After a silent refresh (api_client 401 retry)."""
    _state["access"] = access
    if refresh:
        _state["refresh"] = refresh
    _schedule(_save)


def is_dev_session() -> bool:
    """True for the DEV_MODE "Skip as ..." login (fake token, the API will reject it)."""
    return _state["access"] == "dev"


def clear() -> None:
    _state.update(access=None, refresh=None, user=None)
    _schedule(_forget)


def is_logged_in() -> bool:
    return _state["user"] is not None


def access_token():
    return _state["access"]


def refresh_token():
    return _state["refresh"]


def user() -> dict:
    return _state["user"] or {}


def role():
    return user().get("role")


def is_staff() -> bool:
    """True for PHO/admin users (see config.STAFF_ROLES)."""
    return str(role() or "").strip().lower() in config.STAFF_ROLES