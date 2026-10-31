"""REPORT ISSUE  |  side: student  |  route: /report  |  navbar tab 2
Core feature of the app. Start from the working camera + GPS test code (copy it from the old CampusCare-SL main.py).

UI TODO (form, top to bottom)
  [ ] Dropdown   "Category"            (options from backend: plumbing, electrical, civil, housekeeping, network, ...)
  [ ] TextField  "Description"         (multiline, max ~500 chars, live counter)
  [ ] Photos     Camera preview + "Take photo" button; thumbnails (max 3) with remove (x); "Retake"
  [ ] Location   Button "Use my location" -> shows "Lat, Lng (+/- accuracy m)"
                 Warning chip if accuracy is worse than ~30 m or location is outside campus
  [ ] Dropdown   "Building"            (auto-selected from backend match after GPS; manual fallback if GPS fails/denied)
  [ ] TextField  "Room / exact spot"   (optional)
  [ ] Button     "Submit report"       (disabled until category + description + building are filled; spinner while sending)
  [ ] Success state: "Report submitted, ID #123" -> go(page, "/issue", id=123, replace=True)
  [ ] Error banner + keep the form data on failure

Behaviour TODO
  [ ] Request camera + location permissions; handle "denied" gracefully
  [ ] Compress photo before upload (keep it small for campus Wi-Fi)
  [ ] Submit in 2 steps: issue_service.create_issue(payload incl. idempotency key), then upload_photo() per photo with retry
  [ ] (later) offline draft queue: save locally and retry when online
"""
# import flet as ft


# def view(page: ft.Page, **params) -> ft.Control:
#     return ft.Container(
#         padding=16,
#         content=ft.Column([ft.Text("Report an issue", size=22, weight=ft.FontWeight.BOLD), ft.Text("TODO: see docstring")]),
#     )

"""CampusCare - Report Issue screen.

Route: /report
Side: student

Features:
- Category and building selection
- Description with a 500-character limit
- Photo selection, previews, removal, and a maximum of 3 photos
- Location acquisition when a compatible geolocation plugin is installed
- Form validation
- Two-stage submission through an available issue service
- Loading indicator, success state, and error handling

Only this screen file needs to be modified.
"""

import asyncio
import base64
import importlib
import inspect
import io
import json
import logging
import uuid
from pathlib import Path

import flet as ft
from PIL import Image
from flet_camera import Camera, ResolutionPreset
from flet_geolocator import Geolocator

from core.router import go

logger = logging.getLogger(__name__)

MAX_DESCRIPTION_LENGTH = 500
MAX_PHOTOS = 3
MAX_PHOTO_BYTES = 1_500_000

# Fallback values used until the backend supplies these lists.
DEFAULT_CATEGORIES = [
    "plumbing",
    "electrical",
    "civil",
    "housekeeping",
    "network",
    "furniture",
    "lighting",
    "other",
]

# Replace with backend-provided building data when available.
DEFAULT_BUILDINGS = []


def _control_value(control):
    """Return a control's current value safely."""
    return getattr(control, "value", None)


async def _resolve(value):
    """Await a value if it is awaitable."""
    if inspect.isawaitable(value):
        return await value
    return value


def _find_service():
    """Find a possible issue service without changing other files.

    Supported module candidates:
        services.issue_service
        services.issues
        services.issue
    """
    candidates = (
        "services.issue_service",
        "services.issues",
        "services.issue",
    )

    for module_name in candidates:
        try:
            module = importlib.import_module(module_name)

            create = getattr(module, "create_issue", None)
            upload = getattr(module, "upload_photo", None)

            if callable(create):
                return module, create, upload

        except ImportError:
            continue
        except Exception:
            logger.exception(
                "Unable to load issue service %s", module_name
            )

    return None, None, None


def _category_options():
    """Try to retrieve categories from the backend."""
    possible_modules = (
        "services.issue_service",
        "services.issues",
        "services.issue",
    )

    for module_name in possible_modules:
        try:
            module = importlib.import_module(module_name)

            for name in ("get_categories", "list_categories"):
                function = getattr(module, name, None)

                if not callable(function):
                    continue

                result = function()

                # A synchronous backend lookup is supported here.
                # An async lookup is handled later by the form.
                if inspect.isawaitable(result):
                    continue

                if isinstance(result, (list, tuple)):
                    values = []

                    for item in result:
                        if isinstance(item, dict):
                            value = (
                                item.get("value")
                                or item.get("slug")
                                or item.get("name")
                            )
                        else:
                            value = str(item)

                        if value:
                            values.append(str(value))

                    if values:
                        return values

        except Exception:
            logger.debug(
                "Could not load categories from %s",
                module_name,
                exc_info=True,
            )

    return DEFAULT_CATEGORIES.copy()


def _building_options():
    """Try to retrieve buildings from an existing backend service."""
    possible_modules = (
        "services.issue_service",
        "services.issues",
        "services.issue",
        "services.building_service",
        "services.buildings",
    )

    for module_name in possible_modules:
        try:
            module = importlib.import_module(module_name)

            for name in ("get_buildings", "list_buildings"):
                function = getattr(module, name, None)

                if not callable(function):
                    continue

                result = function()

                if inspect.isawaitable(result):
                    continue

                if isinstance(result, (list, tuple)):
                    values = []

                    for item in result:
                        if isinstance(item, dict):
                            value = (
                                item.get("name")
                                or item.get("building_name")
                            )
                        else:
                            value = str(item)

                        if value:
                            values.append(str(value))

                    if values:
                        return values

        except Exception:
            logger.debug(
                "Could not load buildings from %s",
                module_name,
                exc_info=True,
            )

    return DEFAULT_BUILDINGS.copy()


def view(page: ft.Page, **params) -> ft.Control:
    """Build the Report Issue page."""

    categories = _category_options()
    buildings = _building_options()

    # ---------------------------------------------------------
    # Form state
    # ---------------------------------------------------------

    selected_photos = []
    current_location = {
        "latitude": None,
        "longitude": None,
        "accuracy": None,
    }

    submission_in_progress = False

    # ---------------------------------------------------------
    # UI helpers
    # ---------------------------------------------------------

    title = ft.Text(
        "Report an issue",
        size=26,
        weight=ft.FontWeight.BOLD,
        color=ft.Colors.DEEP_PURPLE_900,
    )

    subtitle = ft.Text(
        "Help keep your campus safe, clean, and functional.",
        size=14,
        color=ft.Colors.GREY_700,
    )

    error_banner = ft.Container(
        visible=False,
        padding=12,
        border_radius=10,
        bgcolor=ft.Colors.RED_50,
        content=ft.Row(
            [
                ft.Icon(
                    ft.Icons.ERROR_OUTLINE,
                    color=ft.Colors.RED_700,
                ),
                ft.Text(
                    "",
                    expand=True,
                    color=ft.Colors.RED_900,
                ),
            ],
            spacing=10,
        ),
    )

    success_panel = ft.Container(
        visible=False,
        padding=20,
        border_radius=12,
        bgcolor=ft.Colors.PURPLE_50,
        content=ft.Column(
            [
                ft.Icon(
                    ft.Icons.CHECK_CIRCLE_OUTLINE,
                    size=48,
                    color=ft.Colors.DEEP_PURPLE_600,
                ),
                ft.Text(
                    "Report submitted successfully!",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(""),
                ft.Button(
                    "View report",
                    icon=ft.Icons.ARROW_FORWARD,
                    on_click=lambda e: go(
                        page,
                        "/issues",
                        replace=True,
                    ),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )

    def show_error(message):
        error_banner.content.controls[1].value = message
        error_banner.visible = True

    def clear_error():
        error_banner.visible = False

    def show_validation_errors():
        """Reveal inline validation messages after the user tries to submit."""
        nonlocal validation_attempted
        validation_attempted = True
        validate_form()
        show_error("Please check the highlighted fields and correct the errors.")
        page.update()

    # ---------------------------------------------------------
    # Category
    # ---------------------------------------------------------

    category_dropdown = ft.Dropdown(
        label="Category",
        hint_text="Select an issue category",
        options=[
            ft.dropdown.Option(
                item,
                text=item.replace("_", " ").title(),
                style=ft.TextStyle(color=ft.Colors.GREY_900),
            )
            for item in categories
        ],
        bgcolor=ft.Colors.WHITE,
        color=ft.Colors.GREY_900,
        text_style=ft.TextStyle(color=ft.Colors.GREY_900, size=14),
        label_style=ft.TextStyle(color=ft.Colors.GREY_700),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_600),
        border_color=ft.Colors.PURPLE_100,
        focused_border_color=ft.Colors.DEEP_PURPLE_600,
        expand=True,
    )

    category_error = ft.Text(
        "", size=12, color=ft.Colors.RED_700, visible=False
    )

    # ---------------------------------------------------------
    # Description
    # ---------------------------------------------------------

    description_field = ft.TextField(
        label="Description",
        hint_text="Describe the problem and where it occurred...",
        multiline=True,
        min_lines=3,
        max_lines=5,
        max_length=MAX_DESCRIPTION_LENGTH,
        capitalization=ft.TextCapitalization.SENTENCES,
        bgcolor=ft.Colors.WHITE,
        color=ft.Colors.GREY_900,
        border_color=ft.Colors.PURPLE_100,
        focused_border_color=ft.Colors.DEEP_PURPLE_600,
        expand=True,
    )

    description_counter = ft.Text(
        "0 / 500",
        size=12,
        color=ft.Colors.GREY_600,
    )
    description_error = ft.Text(
        "", size=12, color=ft.Colors.RED_700, visible=False
    )

    # ---------------------------------------------------------
    # Photos: camera capture + gallery picker
    # ---------------------------------------------------------

    selected_photos = []
    camera_control = None

    photo_strip = ft.Row(controls=[], spacing=10, wrap=True)

    camera_status = ft.Text(
        "No photos selected. You can attach up to 3 photos.",
        size=13,
        color=ft.Colors.GREY_700,
    )

    file_picker = ft.FilePicker()
    camera_preview_container = ft.Container(visible=False)

    def update_photo_ui():
        photo_strip.controls.clear()

        for index, photo in enumerate(selected_photos):
            photo_card = ft.Container(
                width=112,
                padding=6,
                border=ft.Border.all(1, ft.Colors.GREY_300),
                border_radius=10,
                content=ft.Column(
                    [
                        ft.Image(
                            src_base64=base64.b64encode(photo["bytes"]).decode("ascii"),
                            width=96,
                            height=82,
                            fit=ft.ImageFit.COVER,
                            border_radius=8,
                        ),
                        ft.Text(
                            photo.get("name", "Photo"),
                            size=10,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Row(
                            [
                                ft.IconButton(
                                    icon=ft.Icons.CLOSE,
                                    icon_size=17,
                                    tooltip="Remove photo",
                                    on_click=lambda e, i=index: remove_photo(i),
                                ),
                            ],
                            alignment=ft.MainAxisAlignment.CENTER,
                            spacing=0,
                        ),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            )
            photo_strip.controls.append(photo_card)

        camera_status.value = (
            f"{len(selected_photos)} of {MAX_PHOTOS} photos selected."
            if selected_photos
            else "No photos selected. You can attach up to 3 photos."
        )
        page.update()

    def remove_photo(index):
        if 0 <= index < len(selected_photos):
            selected_photos.pop(index)
            update_photo_ui()
            validate_form()

    def _compress_photo(photo_bytes, name):
        """Normalize images to JPEG and compress them for mobile uploads."""
        if not photo_bytes:
            raise ValueError("The image is empty.")

        try:
            with Image.open(io.BytesIO(photo_bytes)) as source:
                source.load()
                image = source.convert("RGB")
                image.thumbnail((1600, 1600))
                quality = 85
                output = io.BytesIO()
                image.save(output, format="JPEG", quality=quality, optimize=True)
                while output.tell() > MAX_PHOTO_BYTES and quality > 40:
                    quality -= 10
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=quality, optimize=True)
                while output.tell() > MAX_PHOTO_BYTES and max(image.size) > 640:
                    image.thumbnail((int(image.width * 0.8), int(image.height * 0.8)))
                    output = io.BytesIO()
                    image.save(output, format="JPEG", quality=70, optimize=True)
                compressed = output.getvalue()
        except Exception as exc:
            raise ValueError(f"Could not read/compress this image: {exc}") from exc

        if len(compressed) > MAX_PHOTO_BYTES:
            raise ValueError("The photo could not be compressed below 1.5 MB.")
        base_name = Path(name).stem or "campuscare_photo"
        return compressed, f"{base_name}.jpg"

    def _add_photo_bytes(photo_bytes, name):
        """Compress and add in-memory image bytes, enforcing count limits."""
        if len(selected_photos) >= MAX_PHOTOS:
            show_error("You can attach a maximum of 3 photos.")
            page.update()
            return False
        if not photo_bytes:
            show_error("The camera did not return an image. Please try again.")
            page.update()
            return False
        try:
            photo_bytes, name = _compress_photo(bytes(photo_bytes), name)
        except Exception as exc:
            show_error(f"Could not prepare {name} for upload: {exc}")
            page.update()
            return False

        selected_photos.append({
            "path": None,
            "bytes": bytes(photo_bytes),
            "name": name,
            "size": len(photo_bytes),
        })
        clear_error()
        update_photo_ui()
        validate_form()
        return True

    async def close_camera(e=None):
        nonlocal camera_control
        camera_preview_container.visible = False
        camera_preview_container.content = None
        camera_control = None
        page.update()

    async def capture_camera_photo(e=None):
        if camera_control is None:
            show_error("Camera is not ready. Please open it again.")
            page.update()
            return
        if len(selected_photos) >= MAX_PHOTOS:
            show_error("You can attach a maximum of 3 photos.")
            page.update()
            return

        try:
            camera_status.value = "Capturing photo..."
            page.update()
            image_bytes = await _resolve(camera_control.take_picture())
            if _add_photo_bytes(image_bytes, f"campuscare_{uuid.uuid4().hex[:8]}.jpg"):
                await close_camera()
        except Exception as exc:
            logger.exception("Camera capture failed")
            camera_status.value = "Could not capture photo. Please try again."
            show_error(
                "Unable to capture a photo. Check camera permission and try again. "
                f"Details: {exc}"
            )
            page.update()

    async def open_camera(e=None):
        nonlocal camera_control
        if len(selected_photos) >= MAX_PHOTOS:
            show_error("You can attach a maximum of 3 photos.")
            page.update()
            return

        clear_error()
        camera_status.value = "Opening camera..."
        page.update()

        try:
            if camera_control is None:
                camera_control = Camera(preview_enabled=True)
                camera_preview_container.content = ft.Column(
                    [
                        camera_control,
                        ft.Row(
                            [
                                ft.Button(
                                    "Capture photo",
                                    icon=ft.Icons.CAMERA_ALT,
                                    on_click=capture_camera_photo,
                                    bgcolor=ft.Colors.DEEP_PURPLE_600,
                                    color=ft.Colors.WHITE,
                                    expand=True,
                                ),
                                ft.Button(
                                    "Cancel",
                                    on_click=close_camera,
                                    bgcolor=ft.Colors.GREY_200,
                                    color=ft.Colors.GREY_900,
                                ),
                            ],
                            spacing=8,
                        ),
                    ],
                    spacing=10,
                )
            camera_preview_container.visible = True
            page.update()

            cameras = await _resolve(camera_control.get_available_cameras())
            if not cameras:
                raise RuntimeError(
                    "No camera was found. Check that this device has a camera and "
                    "that camera permission is enabled."
                )

            # Medium resolution keeps captures suitable for campus Wi-Fi uploads.
            await _resolve(
                camera_control.initialize(
                    cameras[0],
                    ResolutionPreset.medium,
                    enable_audio=False,
                )
            )
            camera_status.value = "Camera ready. Capture a photo or cancel."
            page.update()

        except Exception as exc:
            logger.exception("Could not initialize camera")
            camera_preview_container.visible = False
            camera_preview_container.content = None
            camera_control = None
            camera_status.value = "Camera unavailable. You can choose an existing photo instead."
            error_text = str(exc)
            permission_problem = any(
                word in error_text.lower()
                for word in ("permission", "denied", "cameraaccess")
            )
            if permission_problem:
                show_error(
                    "Android did not grant camera access. Opening CampusCare app settings; "
                    "enable Camera permission, return to the app, and tap Take photo again. "
                    f"Details: {exc}"
                )
                page.update()
                try:
                    await _resolve(geolocator.open_app_settings())
                except Exception:
                    logger.exception("Could not open app settings for camera permission")
            else:
                show_error(
                    "Unable to open the camera. You can still choose a photo from the gallery. "
                    f"Details: {exc}"
                )
                page.update()

    async def handle_file_picker_result(e):
        files = getattr(e, "files", None) or []
        if not files:
            return

        available_slots = MAX_PHOTOS - len(selected_photos)
        if available_slots <= 0:
            show_error("You can attach a maximum of 3 photos.")
            page.update()
            return

        added = 0
        for picked_file in files[:available_slots]:
            file_name = getattr(picked_file, "name", None) or "photo"
            suffix = Path(file_name).suffix.lower()
            if suffix not in (".jpg", ".jpeg", ".png", ".webp"):
                show_error(f"{file_name} is not supported. Use JPG, PNG, or WEBP.")
                continue

            try:
                raw_bytes = getattr(picked_file, "bytes", None)
                path_value = getattr(picked_file, "path", None)
                if raw_bytes:
                    photo_bytes = bytes(raw_bytes)
                elif path_value:
                    with open(path_value, "rb") as image_file:
                        photo_bytes = image_file.read()
                else:
                    show_error(f"Could not read {file_name}. Please choose it again.")
                    continue

                try:
                    photo_bytes, compressed_name = _compress_photo(photo_bytes, file_name)
                except Exception as exc:
                    show_error(f"Could not prepare {file_name} for upload: {exc}")
                    continue

                selected_photos.append({
                    "path": None,
                    "bytes": photo_bytes,
                    "name": compressed_name,
                    "size": len(photo_bytes),
                })
                added += 1
            except (OSError, TypeError, ValueError):
                logger.exception("Unable to read selected photo")
                show_error(f"Unable to read {file_name}. Please try another image.")

        if added:
            clear_error()
        update_photo_ui()
        validate_form()
        page.update()

    file_picker.on_result = handle_file_picker_result

    async def choose_photos(e=None):
        remaining = MAX_PHOTOS - len(selected_photos)
        if remaining <= 0:
            show_error("You can attach a maximum of 3 photos.")
            page.update()
            return
        clear_error()
        try:
            await file_picker.pick_files(
                dialog_title="Choose issue photos",
                allow_multiple=True,
                file_type=ft.FilePickerFileType.IMAGE,
                with_data=True,
            )
        except Exception as exc:
            logger.exception("Photo picker failed")
            show_error(f"Unable to open the photo picker. Details: {exc}")
            page.update()

    take_photo_button = ft.Button(
        "Take photo",
        icon=ft.Icons.CAMERA_ALT,
        on_click=open_camera,
        bgcolor=ft.Colors.DEEP_PURPLE_600,
        color=ft.Colors.WHITE,
    )
    choose_gallery_button = ft.Button(
        "Choose from gallery",
        icon=ft.Icons.PHOTO_LIBRARY_OUTLINED,
        on_click=choose_photos,
        bgcolor=ft.Colors.DEEP_PURPLE_50,
        color=ft.Colors.DEEP_PURPLE_700,
    )

    # ---------------------------------------------------------
    # Location: actual flet-geolocator API
    # ---------------------------------------------------------

    location_status = ft.Text(
        "Location has not been fetched.",
        size=13,
        color=ft.Colors.GREY_700,
    )

    location_warning = ft.Container(
        visible=False,
        padding=8,
        border_radius=8,
        bgcolor=ft.Colors.AMBER_100,
        content=ft.Row(
            [
                ft.Icon(ft.Icons.WARNING_AMBER, color=ft.Colors.AMBER_900, size=18),
                ft.Text("", size=12, color=ft.Colors.AMBER_900, expand=True),
            ],
            spacing=8,
        ),
    )

    geolocator = Geolocator()
    # Geolocator is a Flet service/control and should be registered with the page.
    try:
        page.services.append(geolocator)
    except Exception:
        logger.debug("Geolocator service could not be registered", exc_info=True)

    async def _auto_match_building(latitude, longitude):
        """Try existing optional building-match services; never block manual selection."""
        for module_name in (
            "services.issue_service",
            "services.issues",
            "services.issue",
            "services.building_service",
            "services.buildings",
        ):
            try:
                module = importlib.import_module(module_name)
                matcher = getattr(module, "match_building", None)
                if not callable(matcher):
                    continue
                try:
                    signature = inspect.signature(matcher)
                    positional = [
                        p for p in signature.parameters.values()
                        if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD)
                    ]
                except (TypeError, ValueError):
                    positional = []

                if len(positional) >= 2:
                    match_result = matcher(latitude, longitude)
                else:
                    match_result = matcher({"latitude": latitude, "longitude": longitude})
                match_result = await _resolve(match_result)

                if isinstance(match_result, dict):
                    match_name = (
                        match_result.get("name")
                        or match_result.get("building")
                        or match_result.get("building_name")
                    )
                elif isinstance(match_result, str):
                    match_name = match_result
                else:
                    match_name = None

                if match_name:
                    match_name = str(match_name)
                    existing = {getattr(option, "key", None) for option in building_dropdown.options}
                    if match_name not in existing:
                        building_dropdown.options.append(ft.dropdown.Option(match_name, text=match_name))
                    building_dropdown.value = match_name
                    building_note.value = f"Building detected automatically: {match_name}. You can change it."
                    return True
            except Exception:
                logger.debug("Automatic building matching failed via %s", module_name, exc_info=True)
        return False

    async def get_location(e=None):
        clear_error()
        location_status.value = "Requesting location permission..."
        location_warning.visible = False
        page.update()

        try:
            permission_status = await _resolve(geolocator.request_permission())
            permission_name = getattr(permission_status, "name", str(permission_status)).lower()
            if "deniedforever" in permission_name or "denied_forever" in permission_name:
                location_status.value = "Location permission is blocked in Android settings."
                page.update()
                await _resolve(geolocator.open_app_settings())
                return
            if "denied" in permission_name or "unable" in permission_name:
                location_status.value = "Location permission was not granted. Tap again to retry."
                show_error(
                    "Please allow location access when Android asks. If you previously blocked it, "
                    "open Android Settings > Apps > CampusCare > Permissions > Location."
                )
                page.update()
                return

            service_enabled = await _resolve(geolocator.is_location_service_enabled())
            if not service_enabled:
                location_status.value = "GPS is off. Turn on Location, then return here."
                show_error("Android will open Location settings. Turn Location on, return to CampusCare, and tap Use my location again.")
                page.update()
                try:
                    await _resolve(geolocator.open_location_settings())
                except Exception:
                    logger.exception("Could not open Android Location settings")
                return

            location_status.value = "Getting your current GPS position..."
            page.update()
            position = await _resolve(geolocator.get_current_position())
            latitude = getattr(position, "latitude", None)
            longitude = getattr(position, "longitude", None)
            accuracy = getattr(position, "accuracy", None)

            if latitude is None or longitude is None:
                raise RuntimeError("The GPS service did not return valid coordinates.")

            current_location["latitude"] = float(latitude)
            current_location["longitude"] = float(longitude)
            current_location["accuracy"] = float(accuracy) if accuracy is not None else None

            accuracy_text = (
                f" ±{float(accuracy):.1f} m accuracy"
                if accuracy is not None
                else " accuracy unavailable"
            )
            location_status.value = (
                f"Latitude: {float(latitude):.6f}\n"
                f"Longitude: {float(longitude):.6f}{accuracy_text}"
            )

            if accuracy is not None and float(accuracy) > 30:
                location_warning.visible = True
                location_warning.content.controls[1].value = (
                    f"GPS accuracy is about {float(accuracy):.0f} m. "
                    "Try again outdoors for a more precise location."
                )

            matched = await _auto_match_building(float(latitude), float(longitude))
            if not matched:
                building_note.value = "Location fetched. Choose your building manually if needed."

            clear_error()
        except Exception as exc:
            logger.exception("Could not get current location")
            location_status.value = "Location unavailable. You can still select a building manually."
            show_error(str(exc))
        page.update()

    location_button = ft.Button(
        "Use my location",
        icon=ft.Icons.MY_LOCATION,
        on_click=get_location,
        bgcolor=ft.Colors.DEEP_PURPLE_50,
        color=ft.Colors.DEEP_PURPLE_700,
    )

    # ---------------------------------------------------------
    # Building
    # ---------------------------------------------------------

    building_dropdown = ft.Dropdown(
        label="Building",
        hint_text="Select your building",
        options=[
            ft.dropdown.Option(
                item,
                text=item,
                style=ft.TextStyle(color=ft.Colors.GREY_900),
            )
            for item in buildings
        ],
        bgcolor=ft.Colors.WHITE,
        color=ft.Colors.GREY_900,
        text_style=ft.TextStyle(color=ft.Colors.GREY_900, size=14),
        label_style=ft.TextStyle(color=ft.Colors.GREY_700),
        hint_style=ft.TextStyle(color=ft.Colors.GREY_600),
        border_color=ft.Colors.PURPLE_100,
        focused_border_color=ft.Colors.DEEP_PURPLE_600,
        expand=True,
    )

    building_error = ft.Text(
        "", size=12, color=ft.Colors.RED_700, visible=False
    )

    building_note = ft.Text(
        "Choose your building manually if automatic detection is unavailable.",
        size=12,
        color=ft.Colors.GREY_600,
    )

    room_field = ft.TextField(
        label="Room / exact spot (optional)",
        hint_text="e.g. Room 203, near the library entrance",
        max_length=150,
        bgcolor=ft.Colors.WHITE,
        color=ft.Colors.GREY_900,
        border_color=ft.Colors.PURPLE_100,
        focused_border_color=ft.Colors.DEEP_PURPLE_600,
    )

    # ---------------------------------------------------------
    # Submit button
    # ---------------------------------------------------------

    submit_button = ft.Button(
        "Submit report",
        icon=ft.Icons.SEND,
        disabled=True,
        expand=True,
        bgcolor=ft.Colors.DEEP_PURPLE_600,
        color=ft.Colors.WHITE,
    )

    submit_spinner = ft.ProgressRing(
        width=20,
        height=20,
        stroke_width=3,
        visible=False,
    )

    validation_attempted = False

    def _set_inline_error(control, message):
        control.value = message
        control.visible = bool(message)

    def validate_form(e=None):
        """Validate required fields and show helpful inline feedback."""
        category = (_control_value(category_dropdown) or "").strip()
        description = (_control_value(description_field) or "").strip()
        building = (_control_value(building_dropdown) or "").strip()

        category_message = "Please select an issue category." if not category else ""
        description_message = ""
        if not description:
            description_message = "Please describe the issue."
        elif len(description) < 10:
            description_message = "Please enter at least 10 characters."
        elif len(description) > MAX_DESCRIPTION_LENGTH:
            description_message = "Description must be 500 characters or fewer."

        building_message = "Please select the building where the issue occurred." if not building else ""

        # Avoid showing red errors before the user has interacted with the form.
        if validation_attempted:
            _set_inline_error(category_error, category_message)
            _set_inline_error(description_error, description_message)
            _set_inline_error(building_error, building_message)
        else:
            _set_inline_error(category_error, "")
            _set_inline_error(description_error, "")
            _set_inline_error(building_error, "")

        is_valid = bool(
            category
            and description
            and len(description) >= 10
            and len(description) <= MAX_DESCRIPTION_LENGTH
            and building
            and not submission_in_progress
        )
        submit_button.disabled = not is_valid

        if page:
            page.update()

        return is_valid

    def handle_description_change(e):
        text = _control_value(description_field) or ""
        description_counter.value = f"{len(text)} / {MAX_DESCRIPTION_LENGTH}"
        if validation_attempted:
            validate_form()
        else:
            # Enable/disable the submit button without showing errors yet.
            validate_form()

    def handle_required_change(e):
        validate_form()
        if validation_attempted:
            clear_error()
            # Keep validation visible until each field is corrected.
            validate_form()

    category_dropdown.on_change = handle_required_change
    building_dropdown.on_change = handle_required_change
    description_field.on_change = handle_description_change



    # ---------------------------------------------------------
    # Submission helpers
    # ---------------------------------------------------------

    async def call_create_issue(create_function, payload):
        """Call the discovered issue creation function.

        This adapter assumes create_issue accepts one payload
        argument. If your service has a different signature, this
        function must be adapted to that existing service.
        """
        return await _resolve(create_function(payload))

    async def upload_with_retry(upload_function, issue_id, photo):
        """Upload one photo with up to 3 attempts."""
        if not callable(upload_function):
            raise RuntimeError(
                "The issue service does not expose upload_photo(). "
                "The issue may have been created, but photos cannot "
                "be uploaded until the service is connected."
            )

        last_error = None

        for attempt in range(3):
            try:
                if photo.get("bytes") is not None:
                    photo_bytes = photo["bytes"]
                elif photo.get("path"):
                    with open(photo["path"], "rb") as file:
                        photo_bytes = file.read()
                else:
                    raise RuntimeError(
                        f"Photo data for {photo['name']} is unavailable."
                    )

                result = upload_function(
                    issue_id,
                    photo_bytes,
                    photo["name"],
                )

                return await _resolve(result)

            except Exception as exc:
                last_error = exc

                if attempt < 2:
                    await asyncio.sleep(0.5 * (attempt + 1))

        raise RuntimeError(
            f"Could not upload {photo['name']} after 3 attempts: "
            f"{last_error}"
        )

    async def submit_report(e=None):
        nonlocal submission_in_progress

        nonlocal validation_attempted

        if submission_in_progress:
            return

        validation_attempted = True
        if not validate_form():
            show_error("Please check the highlighted fields and correct the errors.")
            page.update()
            return

        category = _control_value(category_dropdown)
        description = (_control_value(description_field) or "").strip()
        building = _control_value(building_dropdown)
        room = (_control_value(room_field) or "").strip()

        if not category:
            show_error("Please select a category.")
            page.update()
            return

        if not description or len(description) < 10:
            show_error("Description must contain at least 10 characters.")
            page.update()
            return

        if len(description) > MAX_DESCRIPTION_LENGTH:
            show_error("The description cannot exceed 500 characters.")
            page.update()
            return

        if not building:
            show_error("Please select a building.")
            page.update()
            return

        service_module, create_function, upload_function = _find_service()

        if create_function is None:
            show_error(
                "Issue submission is not connected to a backend service. "
                "Please connect the existing create_issue() service "
                "before submitting reports."
            )
            page.update()
            return

        submission_in_progress = True
        submit_button.disabled = True
        submit_button.text = "Submitting..."
        submit_spinner.visible = True
        clear_error()
        page.update()

        idempotency_key = str(uuid.uuid4())

        payload = {
            "category": category,
            "description": description,
            "building": building,
            "room": room or None,
            "location": (
                {
                    "latitude": current_location["latitude"],
                    "longitude": current_location["longitude"],
                    "accuracy": current_location["accuracy"],
                }
                if current_location["latitude"] is not None
                else None
            ),
            "idempotency_key": idempotency_key,
        }

        try:
            # Step 1: Create the report.
            result = await call_create_issue(
                create_function,
                payload,
            )

            if not isinstance(result, dict):
                raise RuntimeError(
                    "The issue service returned an unexpected response."
                )

            issue_id = (
                result.get("id")
                or result.get("issue_id")
                or result.get("report_id")
            )

            if issue_id is None:
                raise RuntimeError(
                    "The backend did not return an issue ID."
                )

            # Step 2: Upload photos individually.
            if selected_photos:
                if not callable(upload_function):
                    raise RuntimeError(
                        f"Report #{issue_id} was created, but photo "
                        "upload is not configured in the issue service."
                    )

                for photo in selected_photos:
                    await upload_with_retry(
                        upload_function,
                        issue_id,
                        photo,
                    )

            success_panel.content.controls[2].value = (
                f"Report submitted, ID #{issue_id}"
            )

            success_panel.visible = True

            # Hide the form after successful submission.
            form_content.visible = False

            page.update()

            # Navigate to the singular /issue route expected by
            # the supplied router. The detail screen receives id.
            go(
                page,
                "/issue",
                id=issue_id,
                replace=True,
            )

        except Exception as exc:
            logger.exception("Report submission failed")

            # Preserve all form fields and selected photos.
            show_error(
                "Submission failed. Your form data has been preserved. "
                f"Details: {exc}"
            )

        finally:
            submission_in_progress = False
            submit_spinner.visible = False
            submit_button.text = "Submit report"
            validate_form()
            page.update()

    submit_button.on_click = submit_report

    # ---------------------------------------------------------
    # Form layout - white and purple CampusCare visual theme
    # ---------------------------------------------------------

    def section_card(icon, heading, helper, controls):
        """Consistent white card with a subtle purple outline."""
        header_items = [
            ft.Container(
                width=42,
                height=42,
                border_radius=12,
                bgcolor=ft.Colors.DEEP_PURPLE_50,
                alignment=ft.Alignment.CENTER,
                content=ft.Icon(icon, color=ft.Colors.DEEP_PURPLE_600, size=22),
            ),
            ft.Column(
                [
                    ft.Text(
                        heading,
                        size=16,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.DEEP_PURPLE_900,
                    ),
                    ft.Text(helper, size=12, color=ft.Colors.GREY_600),
                ],
                spacing=3,
                expand=True,
            ),
        ]
        return ft.Container(
            expand=True,
            padding=ft.Padding.all(18),
            border=ft.Border.all(1, ft.Colors.PURPLE_100),
            border_radius=16,
            bgcolor=ft.Colors.WHITE,
            content=ft.Column(
                [
                    ft.Row(header_items, spacing=12, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Container(height=2),
                    *controls,
                ],
                spacing=12,
            ),
        )

    header = ft.Container(
        padding=ft.Padding.only(left=2, top=4, bottom=8),
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            width=48,
                            height=48,
                            border_radius=14,
                            bgcolor=ft.Colors.DEEP_PURPLE_600,
                            alignment=ft.Alignment.CENTER,
                            content=ft.Icon(ft.Icons.REPORT_PROBLEM_OUTLINED, color=ft.Colors.WHITE, size=25),
                        ),
                        ft.Column([title, subtitle], spacing=5, expand=True),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Container(
                    padding=12,
                    border_radius=12,
                    bgcolor=ft.Colors.PURPLE_50,
                    content=ft.Row(
                        [
                            ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.DEEP_PURPLE_600, size=19),
                            ft.Text(
                                "Share a few details so the campus team can resolve it faster.",
                                size=12,
                                color=ft.Colors.DEEP_PURPLE_800,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                ),
            ],
            spacing=14,
        ),
    )

    form_content = ft.Column(
        [
            header,
            section_card(
                ft.Icons.FORMAT_LIST_BULLETED,
                "Issue details",
                "Tell us what needs attention.",
                [
                    category_dropdown,
                    category_error,
                    description_field,
                    ft.Row([ft.Container(expand=True), description_counter]),
                    description_error,
                ],
            ),
            section_card(
                ft.Icons.CAMERA_ALT_OUTLINED,
                "Photos",
                "A clear photo helps the maintenance team understand the issue.",
                [
                    ft.Row([take_photo_button, choose_gallery_button], wrap=True, spacing=8),
                    camera_status,
                    camera_preview_container,
                    photo_strip,
                ],
            ),
            section_card(
                ft.Icons.MY_LOCATION,
                "Location",
                "Help the team find the issue on campus.",
                [location_button, location_status, location_warning],
            ),
            section_card(
                ft.Icons.LOCATION_CITY_OUTLINED,
                "Building and exact spot",
                "Choose a building and add a room or nearby landmark if useful.",
                [building_dropdown, building_error, building_note, room_field],
            ),
            error_banner,
            ft.Container(
                padding=ft.Padding.only(top=4, bottom=12),
                content=ft.Row(
                    [submit_button, submit_spinner],
                    alignment=ft.MainAxisAlignment.CENTER,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=12,
                ),
            ),
        ],
        spacing=16,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    # Register FilePicker as a page service for Flet versions
    # that require controls to be added to the page.
    page.services.append(file_picker)

    # Responsive outer layout: fill the available app area on phones and
    # laptops, while keeping the form comfortably readable on wide screens.
    return ft.Container(
        expand=True,
        bgcolor=ft.Colors.GREY_50,
        padding=ft.Padding.symmetric(
            horizontal=12 if (page.width or 900) < 600 else 24,
            vertical=12 if (page.width or 900) < 600 else 20,
        ),
        content=ft.Row(
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
            vertical_alignment=ft.CrossAxisAlignment.START,
            controls=[
                ft.Container(
                    expand=True,
                    content=ft.Column(
                        [form_content, success_panel],
                        spacing=12,
                        expand=True,
                        scroll=ft.ScrollMode.AUTO,
                    ),
                )
            ],
        ),
    )