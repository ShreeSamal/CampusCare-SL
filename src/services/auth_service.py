
import httpx

import config



async def _post(path: str, payload: dict) -> dict:
    base_url = config.API_BASE_URL.rstrip("/")

    async with httpx.AsyncClient(timeout=config.REQUEST_TIMEOUT_S) as client:
        response = await client.post(
            f"{base_url}{path}",
            json=payload,
        )
        response.raise_for_status()
        return response.json()




def _normalize_session(data: dict) -> dict:
    user_data = data.get("user") or {}
    metadata = user_data.get("user_metadata") or {}

    return {
        "success": True,
        "access": data.get("access_token"),
        "refresh": data.get("refresh_token"),
        "user": _normalize_user(user_data),
    }


def _normalize_user(user_data: dict) -> dict:
    """Flatten a backend user into the session user dict.

    The backend reads role / name / roll / building from public.profiles and returns
    them at the top level; user_metadata is only a fallback (users can edit it).
    """
    metadata = user_data.get("user_metadata") or {}
    return {
        "id": user_data.get("id"),
        "name": user_data.get("full_name") or metadata.get("full_name", ""),
        "email": user_data.get("email", ""),
        "role": user_data.get("role") or "student",
        "roll_number": user_data.get("roll_number") or metadata.get("roll_number"),
        "building_id": user_data.get("building_id") or metadata.get("building_id"),
        "building_name": user_data.get("building_name"),
        "user_metadata": metadata,
    }


async def list_public_buildings() -> list[dict]:
    """[{id, name, zone}] for the signup dropdown (GET /auth/buildings, no login needed)."""
    from core import api_client

    data = await api_client.request("GET", "/auth/buildings", auth=False)
    return data.get("buildings", []) if isinstance(data, dict) else []


async def me() -> dict:
    """Current user's profile from GET /auth/me (needs a valid access token)."""
    from core import api_client

    data = await api_client.request("GET", "/auth/me")
    return _normalize_user(data.get("user") or {})


async def signup(
    full_name: str,
    email: str,
    password: str,
    roll_no: str | None = None,
    building_id: str | None = None,
) -> dict:
    return await _post(
        "/auth/signup",
        {
            "full_name": full_name,
            "email": email,
            "password": password,
            "roll_number": roll_no,
            "building_id": building_id,
        },
    )


async def login(email: str, password: str) -> dict:
    data = await _post(
        "/auth/login",
        {
            "email": email,
            "password": password,
        },
    )
    return _normalize_session(data)


async def verify_otp(email: str, code: str) -> dict:
    data = await _post(
        "/auth/verify-otp",
        {
            "email": email,
            "token": code,
        },
    )
    return _normalize_session(data)


async def resend_otp(email: str) -> dict:
    return await _post(
        "/auth/resend-otp",
        {
            "email": email,
        },
    )


async def refresh(refresh_token: str) -> dict:
    """POST /auth/refresh -> {access, refresh, user}. Raises api_client.ApiError (401 = token rejected)
    or NetworkError. Supabase rotates the refresh token, so always store the returned one."""
    from core import api_client

    data = await api_client.request(
        "POST", "/auth/refresh", json={"refresh_token": refresh_token}, auth=False, _retry=False
    )
    return _normalize_session(data)