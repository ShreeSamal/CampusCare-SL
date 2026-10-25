import logging
import os
import uuid
from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import ValidationError

from dependencies import get_current_user, get_user_supabase
from schemas.issues import CreateIssueRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/issues", tags=["Issues"])

VALID_STATUSES = {"open", "in_progress", "resolved", "closed"}

PHOTO_BUCKET = os.environ.get("ISSUE_PHOTO_BUCKET", "issue-photos")
MAX_PHOTOS = 3
MAX_PHOTO_BYTES = 5 * 1024 * 1024  # server-side hard limit (app compresses to ~1.5 MB)
ALLOWED_PHOTO_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


# ---------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------

@lru_cache(maxsize=1)
def _admin_client():
    """Optional service-role client used only for Storage uploads.

    Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY to enable it. Uploads are
    still scoped to the logged-in user's folder by this code.
    """
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    from supabase import create_client

    return create_client(url, key)


def _storage_client(user_supabase):
    return _admin_client() or user_supabase


def _prepare_photos(photos: list[UploadFile]):
    """Validate and read all photos BEFORE anything is uploaded."""
    photos = [p for p in photos if p and p.filename]
    if len(photos) > MAX_PHOTOS:
        raise HTTPException(
            status_code=422,
            detail=f"You can attach a maximum of {MAX_PHOTOS} photos.",
        )

    prepared = []
    for photo in photos:
        content_type = (photo.content_type or "").lower()
        extension = ALLOWED_PHOTO_TYPES.get(content_type)
        if extension is None:
            raise HTTPException(
                status_code=422,
                detail=f"{photo.filename}: only JPG, PNG or WEBP images are allowed.",
            )

        data = photo.file.read(MAX_PHOTO_BYTES + 1)
        if not data:
            raise HTTPException(status_code=422, detail=f"{photo.filename} is empty.")
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"{photo.filename} is larger than {MAX_PHOTO_BYTES // (1024 * 1024)} MB.",
            )
        prepared.append((data, extension, content_type))
    return prepared


def _upload_photos(storage_client, user_id: str, prepared):
    """Upload photos to Supabase Storage. Returns (public_urls, uploaded_paths)."""
    bucket = storage_client.storage.from_(PHOTO_BUCKET)
    urls: list[str] = []
    paths: list[str] = []

    try:
        for data, extension, content_type in prepared:
            path = f"{user_id}/{uuid.uuid4().hex}.{extension}"
            bucket.upload(
                path=path,
                file=data,
                file_options={"content-type": content_type},
            )
            paths.append(path)
            urls.append(bucket.get_public_url(path))
    except Exception:
        logger.exception("Photo upload to Supabase Storage failed")
        _remove_photos(storage_client, paths)
        raise HTTPException(
            status_code=502,
            detail="Photos could not be uploaded. Please try again.",
        )

    return urls, paths


def _remove_photos(storage_client, paths: list[str]):
    """Best-effort cleanup so failed submissions don't leave orphan files."""
    if not paths:
        return
    try:
        storage_client.storage.from_(PHOTO_BUCKET).remove(paths)
    except Exception:
        logger.exception("Could not clean up uploaded photos: %s", paths)


# ---------------------------------------------------------
# Routes
# ---------------------------------------------------------

@router.get("/buildings")
def get_buildings(
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    """Buildings for the Report Issue dropdown. Assumes a `buildings` table (id, name)."""
    try:
        response = (
            supabase.table("buildings").select("id, name").order("name").execute()
        )
        return {
            "success": True,
            "buildings": [
                {"id": str(row["id"]), "name": row.get("name") or str(row["id"])}
                for row in (response.data or [])
            ],
        }
    except Exception:
        logger.exception("Could not load buildings")
        raise HTTPException(
            status_code=500,
            detail="Unable to load buildings. Please try again.",
        )


@router.post("", status_code=201)
def create_issue(
    category: str = Form(...),
    description: str = Form(...),
    room: str | None = Form(default=None),
    latitude: float | None = Form(default=None),
    longitude: float | None = Form(default=None),
    location_text: str | None = Form(default=None),
    photos: list[UploadFile] = File(default=[]),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    # 1. Validate the text fields with the existing schema.
    try:
        payload = CreateIssueRequest(
            category=category,
            description=description,
            room=room or None,
            latitude=latitude,
            longitude=longitude,
            location_text=location_text or None,
            photo_urls=[],
        )
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail=[
                {"loc": ["body", *e["loc"]], "msg": e["msg"]} for e in exc.errors()
            ],
        )

    # 2. Validate photos, then upload them to Supabase Storage.
    prepared = _prepare_photos(photos)
    storage = _storage_client(supabase)
    photo_urls, uploaded_paths = (
        _upload_photos(storage, user["id"], prepared) if prepared else ([], [])
    )

    # 3. Insert the issue with the photo URLs in the same request.
    issue_data = payload.model_dump()
    issue_data["photo_urls"] = photo_urls
    issue_data["user_id"] = user["id"]
    issue_data["status"] = "open"

    try:
        response = supabase.table("issues").insert(issue_data).execute()
        if not response.data:
            raise HTTPException(
                status_code=500,
                detail="The issue could not be created.",
            )

        return {
            "success": True,
            "message": "Issue reported successfully.",
            "issue": response.data[0],
        }
    except HTTPException:
        _remove_photos(storage, uploaded_paths)
        raise
    except Exception:
        logger.exception("Issue insert failed")
        _remove_photos(storage, uploaded_paths)
        raise HTTPException(
            status_code=500,
            detail="Unable to create the issue. Please try again.",
        )


@router.get("/mine")
def get_my_issues(
    status: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: dict = Depends(get_current_user),
    supabase=Depends(get_user_supabase),
):
    if status is not None and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail="Invalid status filter.",
        )

    try:
        query = (
            supabase.table("issues")
            .select("*", count="exact")
            .eq("user_id", user["id"])
            .order("created_at", desc=True)
            .range(offset, offset + limit - 1)
        )

        if status is not None:
            query = query.eq("status", status)

        response = query.execute()

        return {
            "success": True,
            "issues": response.data or [],
            "count": response.count or 0,
            "limit": limit,
            "offset": offset,
        }
    except Exception:
        raise HTTPException(
            status_code=500,
            detail="Unable to retrieve your issues. Please try again.",
        )