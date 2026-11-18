"""ISSUE SERVICE - calls to the issue endpoints (backend/routers/issues.py) via core/api_client.py.

Implemented
  [x] list_buildings()              GET  /issues/buildings
  [x] create_issue(payload)         POST /issues               (multipart; photos are sent in the same request)
  [x] list_my_issues(status=None)   GET  /issues/mine
  [x] my_summary()                  GET  /issues/mine/summary  (Home: counts, recent, awaiting confirmation)
  [x] get_issue(issue_id)           GET  /issues/{id}          (issue + worker, timeline, comments, feedback, actions)
  [x] add_comment(issue_id, text)   POST /issues/{id}/comments
  [x] confirm(issue_id, rating, feedback)   POST /issues/{id}/confirm   (resolved -> closed + rating)
  [x] reopen(issue_id, reason)      POST /issues/{id}/reopen   (resolved -> in progress / open)
  [x] match_building(lat, lng, acc) GET  /issues/buildings/match (nearest building to a GPS fix, or None)

Later (no backend yet)
  [ ] list_categories()             GET  /categories/
"""
import mimetypes

from core import api_client

# UI filter label (screens) -> backend status value
_STATUS_VALUES = {
    "open": "open",
    "assigned": "assigned",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "resolved": "resolved",
    "closed": "closed",
    "rejected": "rejected",
}


def _status_value(status: str | None) -> str | None:
    if not status or str(status).strip().lower() == "all":
        return None
    return _STATUS_VALUES.get(str(status).strip().lower(), str(status).strip().lower())


async def list_buildings() -> list[dict]:
    """[{id, name}, ...] sorted by name (public.buildings)."""
    data = await api_client.request("GET", "/issues/buildings")
    return data.get("buildings", []) if isinstance(data, dict) else []


async def list_my_issues(status: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    """The logged-in user's issues, newest first. `status` accepts UI labels ("In progress") or backend values."""
    data = await api_client.request(
        "GET",
        "/issues/mine",
        params={"status": _status_value(status), "limit": limit, "offset": offset},
    )
    issues = data.get("issues", []) if isinstance(data, dict) else []
    for issue in issues:
        # Backend stores the building name inside location_text; screens read "building".
        if not issue.get("building") and issue.get("location_text"):
            issue["building"] = issue["location_text"]
    return issues


async def create_issue(payload: dict) -> dict:
    """Create an issue. Returns the created issue row (has "id").

    payload keys: category, description, building_id, building (name), room, location {latitude, longitude},
                  photos [{name, bytes}]  (optional, max 3 - uploaded in the same request)
    """
    location = payload.get("location") or {}
    form = {
        "category": payload.get("category"),
        "description": payload.get("description") or "",
        "building_id": payload.get("building_id"),
        "room": payload.get("room"),
        "location_text": payload.get("building") or payload.get("location_text"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
    }
    files = []
    for photo in payload.get("photos") or []:
        name = photo.get("name") or "photo.jpg"
        mime = mimetypes.guess_type(name)[0] or "image/jpeg"
        files.append(("photos", (name, photo["bytes"], mime)))

    data = await api_client.request("POST", "/issues", data=form, files=files or None)
    return data.get("issue", data) if isinstance(data, dict) else {}


async def my_summary() -> dict:
    """{counts {status: n}, total, active, overdue, recent [issue], awaiting_confirmation [issue]}"""
    return await api_client.request("GET", "/issues/mine/summary")


async def get_issue(issue_id) -> dict:
    """{issue (+building_name, worker, due_at_effective, overdue), timeline, comments, feedback,
    can_confirm, can_reopen, can_comment}. 404 if the issue isn't the student's."""
    return await api_client.request("GET", f"/issues/{int(issue_id)}")


async def add_comment(issue_id, text: str) -> dict:
    return await api_client.request("POST", f"/issues/{int(issue_id)}/comments", json={"text": text})


async def confirm(issue_id, rating: int, feedback: str | None = None) -> dict:
    return await api_client.request(
        "POST", f"/issues/{int(issue_id)}/confirm", json={"rating": int(rating), "feedback": feedback or None}
    )


async def reopen(issue_id, reason: str) -> dict:
    return await api_client.request("POST", f"/issues/{int(issue_id)}/reopen", json={"reason": reason})


async def match_building(latitude: float, longitude: float, accuracy: float | None = None) -> dict | None:
    """Nearest campus building to a GPS fix: {id, name, zone, distance_m, confidence} or None
    (off campus / too far from every building / building coordinates not configured)."""
    data = await api_client.request(
        "GET", "/issues/buildings/match", params={"lat": latitude, "lng": longitude, "accuracy": accuracy}
    )
    return data.get("match") if isinstance(data, dict) else None
