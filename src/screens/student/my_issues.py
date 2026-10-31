"""CampusCare - My Issues screen.

Route: /issues
Side: student

Features:
- Single-select status filters
- Scrollable issue list
- Issue cards with category, description, building, status and date
- Overdue badge
- Navigation to issue details
- Loading, error and retry states
- Empty state for each filter
- Pull-to-refresh-style refresh button

Compatible with the CampusCare router pattern.
"""

import asyncio
import importlib
import inspect
import logging
from datetime import datetime, timedelta, timezone

import flet as ft

from core.router import go

logger = logging.getLogger(__name__)

FILTERS = [
    "All",
    "Open",
    "In progress",
    "Resolved",
    "Closed",
]

# Temporary fallback data used only when no compatible backend
# service is available.
SAMPLE_ISSUES = [
    {
        "id": 1,
        "category": "civil",
        "title": "Pothole near the main gate",
        "description": "There is a large pothole near the main entrance.",
        "building": "Main Gate",
        "status": "Open",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=3),
        "overdue": False,
    },
    {
        "id": 2,
        "category": "electrical",
        "title": "Broken corridor light",
        "description": "The light outside the second-floor classroom is not working.",
        "building": "Academic Building",
        "status": "In progress",
        "created_at": datetime.now(timezone.utc) - timedelta(days=2),
        "overdue": True,
    },
    {
        "id": 3,
        "category": "plumbing",
        "title": "Water leakage",
        "description": "Water is leaking from a pipe near the washroom.",
        "building": "Hostel Building",
        "status": "Resolved",
        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
        "overdue": False,
    },
]


CATEGORY_ICONS = {
    "plumbing": ft.Icons.WATER_DROP,
    "electrical": ft.Icons.BOLT,
    "civil": ft.Icons.CONSTRUCTION,
    "housekeeping": ft.Icons.CLEANING_SERVICES,
    "network": ft.Icons.WIFI,
    "furniture": ft.Icons.CHAIR,
    "lighting": ft.Icons.LIGHTBULB,
    "other": ft.Icons.REPORT_PROBLEM,
}


PURPLE = "#6038B5"
PURPLE_DARK = "#43208F"
PURPLE_LIGHT = "#F2EAFB"
PURPLE_BORDER = "#E5D2F6"
PAGE_BG = "#FCFAFE"
TEXT_PRIMARY = "#29223A"
TEXT_SECONDARY = "#746D80"

STATUS_COLORS = {
    "open": PURPLE,
    "in progress": "#A66A00",
    "resolved": "#27834A",
    "closed": "#77717F",
}


def _normalise_status(value):
    """Convert a status to a consistent display format."""
    value = str(value or "Open").strip().lower()

    if value in ("in_progress", "in-progress", "inprogress"):
        return "In progress"

    if value == "pending":
        return "Open"

    return value.title()


def _parse_datetime(value):
    """Convert supported timestamp values to datetime."""
    if isinstance(value, datetime):
        return value

    if not value:
        return None

    try:
        result = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )

        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)

        return result

    except (ValueError, TypeError):
        return None


def _format_date(value):
    timestamp = _parse_datetime(value)

    if timestamp is None:
        return "Date unavailable"

    return timestamp.strftime("%d %b %Y, %I:%M %p")


def _get_category_icon(category):
    return CATEGORY_ICONS.get(
        str(category or "other").lower(),
        ft.Icons.REPORT_PROBLEM,
    )


def _find_list_service():
    """Find a possible existing list_my_issues service."""
    module_names = (
        "services.issue_service",
        "services.issues",
        "services.issue",
    )

    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
            function = getattr(module, "list_my_issues", None)

            if callable(function):
                return function

        except ImportError:
            continue

        except Exception:
            logger.exception(
                "Could not load issue service %s",
                module_name,
            )

    return None


async def _await_if_needed(value):
    if inspect.isawaitable(value):
        return await value

    return value


async def _fetch_issues(status):
    """Load issues from the available backend.

    If the service is not implemented, sample data is used.
    Backend failures are allowed to propagate so the UI can
    display an error and retry action.
    """
    service = _find_list_service()

    if service is None:
        return [dict(issue) for issue in SAMPLE_ISSUES]

    if status == "All":
        result = await _await_if_needed(service(status=None))
    else:
        result = await _await_if_needed(service(status=status))

    if result is None:
        return []

    # Support a plain list or a common API response structure.
    if isinstance(result, dict):
        result = (
            result.get("items")
            or result.get("issues")
            or result.get("results")
            or []
        )

    if not isinstance(result, (list, tuple)):
        raise RuntimeError(
            "The issue service returned an unsupported response."
        )

    normalised = []

    for item in result:
        if not isinstance(item, dict):
            continue

        created_at = (
            item.get("created_at")
            or item.get("createdAt")
            or item.get("created")
        )

        category = (
            item.get("category")
            or item.get("issue_category")
            or "other"
        )

        description = (
            item.get("description")
            or item.get("title")
            or "No description provided."
        )

        building = (
            item.get("building")
            or item.get("building_name")
            or "Building unavailable"
        )

        if isinstance(building, dict):
            building = building.get("name", "Building unavailable")

        status_value = _normalise_status(
            item.get("status", "Open")
        )

        normalised.append(
            {
                **item,
                "id": item.get("id") or item.get("issue_id"),
                "category": str(category),
                "title": item.get("title") or str(category).title(),
                "description": str(description),
                "building": str(building),
                "status": status_value,
                "created_at": created_at,
                "overdue": bool(item.get("overdue", False)),
            }
        )

    # Newest first.
    normalised.sort(
        key=lambda issue: (
            _parse_datetime(issue.get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )

    return normalised


def view(
    page: ft.Page,
    status: str | None = None,
    **params,
) -> ft.Control:
    """Build the My Issues page."""

    selected_filter = status or "All"

    if selected_filter.lower() == "in_progress":
        selected_filter = "In progress"

    if selected_filter not in FILTERS:
        selected_filter = "All"

    all_issues = []
    is_loading = False
    load_error = None

    title = ft.Text(
        "My issues",
        size=26,
        weight=ft.FontWeight.BOLD,
        color=PURPLE_DARK,
    )

    subtitle = ft.Text(
        "Track the status of issues you have reported.",
        size=14,
        color=TEXT_SECONDARY,
    )

    count_label = ft.Text(
        "",
        size=13,
        color=TEXT_SECONDARY,
    )

    filter_row = ft.Row(
        spacing=8,
        wrap=True,
        scroll=ft.ScrollMode.AUTO,
    )

    issues_list = ft.Column(
        spacing=12,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )

    loading_panel = ft.Container(
        visible=True,
        padding=30,
        content=ft.Column(
            [
                ft.ProgressRing(),
                ft.Text("Loading your issues..."),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )

    error_panel = ft.Container(
        visible=False,
        padding=18,
        border_radius=12,
        bgcolor="#FFF4F4",
        content=ft.Column(
            [
                ft.Icon(
                    ft.Icons.ERROR_OUTLINE,
                    size=36,
                    color=ft.Colors.RED_700,
                ),
                ft.Text(
                    "Couldn't load your issues",
                    size=17,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.RED_900,
                ),
                ft.Text(
                    "",
                    color=ft.Colors.RED_900,
                ),
                ft.Button(
                    "Try again",
                    icon=ft.Icons.REFRESH,
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=10,
        ),
    )

    empty_panel = ft.Container(
        visible=False,
        padding=30,
        content=ft.Column(
            [
                ft.Icon(
                    ft.Icons.INBOX_OUTLINED,
                    size=52,
                    color=PURPLE,
                ),
                ft.Text(
                    "No issues found",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                ),
                ft.Text(
                    "Issues matching this filter will appear here.",
                    color=ft.Colors.GREY_700,
                    text_align=ft.TextAlign.CENTER,
                ),
                ft.Button(
                    "Report an issue",
                    icon=ft.Icons.ADD,
                    on_click=lambda e: go(page, "/report"),
                ),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=12,
        ),
    )

    # ---------------------------------------------------------
    # Issue card
    # ---------------------------------------------------------

    def build_issue_card(issue):
        issue_id = issue.get("id")

        category = str(
            issue.get("category") or "other"
        )

        title_text = str(
            issue.get("title")
            or category.replace("_", " ").title()
        )

        description = str(
            issue.get("description") or ""
        )

        building = str(
            issue.get("building") or "Building unavailable"
        )

        issue_status = _normalise_status(
            issue.get("status")
        )

        status_color = STATUS_COLORS.get(
            issue_status.lower(),
            ft.Colors.GREY,
        )

        overdue = bool(issue.get("overdue", False))

        metadata = [
            ft.Icon(
                ft.Icons.LOCATION_ON_OUTLINED,
                size=16,
                color=ft.Colors.GREY_600,
            ),
            ft.Text(
                building,
                size=12,
                color=ft.Colors.GREY_700,
                expand=True,
            ),
        ]

        if overdue:
            metadata.append(
                ft.Container(
                    padding=ft.Padding.symmetric(
                        horizontal=8,
                        vertical=4,
                    ),
                    border_radius=6,
                    bgcolor=ft.Colors.RED_100,
                    content=ft.Text(
                        "OVERDUE",
                        size=10,
                        weight=ft.FontWeight.BOLD,
                        color=ft.Colors.RED_900,
                    ),
                )
            )

        return ft.Container(
            padding=18,
            bgcolor=ft.Colors.WHITE,
            border=ft.Border.all(1, PURPLE_BORDER),
            border_radius=16,
            shadow=ft.BoxShadow(
                blur_radius=8,
                spread_radius=0,
                color="#10000000",
                offset=ft.Offset(0, 2),
            ),
            ink=True,
            on_click=lambda e, iid=issue_id: go(
                page,
                "/issue",
                id=iid,
            ),
            content=ft.Column(
                [
                    ft.Row(
                        [
                            ft.Container(
                                width=44,
                                height=44,
                                border_radius=10,
                                bgcolor=PURPLE_LIGHT,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(
                                    _get_category_icon(category),
                                    size=23,
                                    color=PURPLE,
                                ),
                            ),
                            ft.Column(
                                [
                                    ft.Text(
                                        title_text,
                                        size=16,
                                        weight=ft.FontWeight.BOLD,
                                        max_lines=2,
                                        overflow=ft.TextOverflow.ELLIPSIS,
                                        expand=True,
                                    ),
                                    ft.Text(
                                        f"#{issue_id}"
                                        if issue_id is not None
                                        else "Issue ID unavailable",
                                        size=11,
                                        color=ft.Colors.GREY_600,
                                    ),
                                ],
                                spacing=3,
                                expand=True,
                            ),
                            ft.Container(
                                padding=ft.Padding.symmetric(
                                    horizontal=9,
                                    vertical=5,
                                ),
                                border_radius=8,
                                bgcolor=status_color,
                                content=ft.Text(
                                    issue_status,
                                    size=11,
                                    color=ft.Colors.WHITE,
                                    weight=ft.FontWeight.BOLD,
                                ),
                            ),
                        ],
                        spacing=10,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Text(
                        description,
                        size=13,
                        color=ft.Colors.GREY_700,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS,
                    ),
                    ft.Row(
                        metadata,
                        spacing=6,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            ft.Icon(
                                ft.Icons.CALENDAR_TODAY_OUTLINED,
                                size=14,
                                color=ft.Colors.GREY_600,
                            ),
                            ft.Text(
                                _format_date(
                                    issue.get("created_at")
                                ),
                                size=11,
                                color=ft.Colors.GREY_600,
                            ),
                            ft.Container(expand=True),
                            ft.Icon(
                                ft.Icons.CHEVRON_RIGHT,
                                color=ft.Colors.GREY_500,
                            ),
                        ],
                        spacing=5,
                    ),
                ],
                spacing=10,
            ),
        )

    # ---------------------------------------------------------
    # Filtering and rendering
    # ---------------------------------------------------------

    def filtered_issues():
        if selected_filter == "All":
            result = list(all_issues)
        else:
            result = [
                issue
                for issue in all_issues
                if _normalise_status(
                    issue.get("status")
                ).lower()
                == selected_filter.lower()
            ]

        result.sort(
            key=lambda issue: (
                _parse_datetime(issue.get("created_at"))
                or datetime.min.replace(tzinfo=timezone.utc)
            ),
            reverse=True,
        )

        return result

    def update_filter_buttons():
        filter_row.controls.clear()

        for filter_name in FILTERS:
            is_selected = filter_name == selected_filter

            filter_row.controls.append(
                ft.Button(
                    filter_name,
                    on_click=lambda e, name=filter_name: select_filter(name),
                    style=ft.ButtonStyle(
                        bgcolor=(
                            PURPLE
                            if is_selected
                            else PURPLE_LIGHT
                        ),
                        color=(
                            ft.Colors.WHITE
                            if is_selected
                            else PURPLE_DARK
                        ),
                        shape=ft.RoundedRectangleBorder(radius=20),
                        padding=ft.Padding.symmetric(
                            horizontal=15,
                            vertical=10,
                        ),
                    ),
                )
            )

    def render_issues():
        issues_list.controls.clear()

        result = filtered_issues()

        count_label.value = (
            f"{len(result)} "
            f"{'issue' if len(result) == 1 else 'issues'}"
        )

        empty_panel.content.controls[1].value = (
            f"No {selected_filter.lower()} issues yet"
            if selected_filter != "All"
            else "No issues reported yet"
        )

        if result:
            issues_list.controls.extend(
                build_issue_card(issue)
                for issue in result
            )

        issues_list.visible = bool(result)
        empty_panel.visible = not result
        loading_panel.visible = False
        error_panel.visible = False

    async def load_issues():
        nonlocal all_issues, is_loading, load_error

        if is_loading:
            return

        is_loading = True
        load_error = None

        loading_panel.visible = True
        error_panel.visible = False
        empty_panel.visible = False
        issues_list.visible = False

        page.update()

        try:
            all_issues = await _fetch_issues(selected_filter)
            render_issues()

        except Exception as exc:
            logger.exception("Failed to load issues")

            load_error = str(exc)
            loading_panel.visible = False
            issues_list.visible = False
            empty_panel.visible = False
            error_panel.visible = True
            error_panel.content.controls[2].value = (
                "Check your connection and try again."
            )

        finally:
            is_loading = False
            page.update()

    def select_filter(filter_name):
        nonlocal selected_filter

        if filter_name not in FILTERS:
            return

        selected_filter = filter_name
        update_filter_buttons()

        # Load data for the selected filter.
        page.run_task(load_issues)

        page.update()

    async def refresh_issues(e=None):
        await load_issues()

    error_panel.content.controls[3].on_click = (
        lambda e: page.run_task(load_issues)
    )

    refresh_button = ft.IconButton(
        icon=ft.Icons.REFRESH,
        tooltip="Refresh issues",
        on_click=lambda e: page.run_task(refresh_issues),
    )

    update_filter_buttons()

    page.run_task(load_issues)

    return ft.Container(
        padding=ft.Padding.only(left=20, right=20, top=18, bottom=16),
        expand=True,
        bgcolor=PAGE_BG,
        content=ft.Column(
            [
                ft.Row(
                    [
                        ft.Column(
                            [
                                title,
                                subtitle,
                            ],
                            spacing=4,
                            expand=True,
                        ),
                        refresh_button,
                    ],
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                ft.Divider(color=PURPLE_BORDER, height=1),
                filter_row,
                count_label,
                loading_panel,
                error_panel,
                empty_panel,
                issues_list,
            ],
            spacing=14,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        ),
    )