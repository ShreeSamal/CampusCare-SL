"""HOME  |  side: student  |  route: /home  |  navbar tab 1

UI TODO
  [=] Header: "Hi, <first name>"
  [=] Summary cards row (3 cards): Open | In progress | Resolved   (counts, tap -> /issues with that filter)
  [=] Primary Button "Report an issue" -> go(page, "/report")
  [ ] "Recent issues" section: last 3-5 issues as IssueCard (components/issue_card.py), tap -> go(page, "/issue", id=...)
  [=] "View all" TextButton -> go(page, "/issues")
  [=] Empty state (no issues yet) with a friendly message + report button
  [=] Loading state (skeleton or ProgressRing) and error state with Retry
  [=] Pull-to-refresh (or a refresh icon)
  [=] No charts on this screen

Data TODO
  [ ] issue_service.list_my_issues() and compute counts (or a dedicated summary endpoint)
"""

from __future__ import annotations

import inspect
from datetime import datetime
from typing import Any

import flet as ft

from components import issue_card as issue_card_component
from components import status_chip as status_chip_component
from core import session
from core.router import go
from services import issue_service


PURPLE = "#7054F6"
PURPLE_DARK = "#392A78"
PURPLE_MID = "#8C79FA"
LAVENDER = "#F0EDFF"
PAGE_BG = "#F8F7FF"
TEXT = "#211B36"
MUTED = "#77728C"
BORDER = "#E8E4F3"
WHITE = "#FFFFFF"
ERROR = "#B4234D"
ERROR_BG = "#FFF0F3"
SUCCESS_BG = "#F0ECFF"

STATUS_COLORS = {
    "open": ("#8A5A00", "#FFF4D6"),
    "in_progress": (PURPLE_DARK, LAVENDER),
    "resolved": ("#176B46", "#E5F7ED"),
    "closed": ("#176B46", "#E5F7ED"),
}


def _first_name() -> str:
    """Return the current user's first name, with a neutral fallback."""
    user = session.user() or {}
    name = str(user.get("name") or user.get("full_name") or "").strip()
    return name.split()[0] if name else "there"


def _normalise_status(issue: dict[str, Any]) -> str:
    value = str(issue.get("status") or "open").strip().lower().replace(" ", "_")
    aliases = {
        "inprogress": "in_progress",
        "in-progress": "in_progress",
        "reported": "open",
        "complete": "resolved",
        "completed": "resolved",
    }
    return aliases.get(value, value)


def _status_label(status: str) -> str:
    return {
        "open": "Open",
        "in_progress": "In progress",
        "resolved": "Resolved",
        "closed": "Closed",
        "assigned": "Assigned",
        "acknowledged": "Acknowledged",
        "reopened": "Reopened",
    }.get(status, status.replace("_", " ").title() or "Open")


def _issue_date(value: Any) -> str:
    if not value:
        return "Date unavailable"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed.strftime("%d %b %Y")
    except (TypeError, ValueError):
        return str(value)[:10]


def _issue_location(issue: dict[str, Any]) -> str:
    pieces = [
        str(issue.get("building_name") or issue.get("building") or issue.get("building_id") or "").strip(),
        str(issue.get("room") or "").strip(),
    ]
    location = " · ".join(piece for piece in pieces if piece)
    return location or str(issue.get("location_text") or "Campus location")


def _issue_title(issue: dict[str, Any]) -> str:
    category = str(issue.get("category") or "Campus issue").strip()
    return category.replace("_", " ").title()


def _load_issue_list(result: Any) -> list[dict[str, Any]]:
    """Accept the common list/dict response shapes used by the service layer."""
    if isinstance(result, list):
        items = result
    elif isinstance(result, dict):
        if result.get("success") is False or result.get("error"):
            message = result.get("detail") or result.get("message") or result.get("error")
            raise RuntimeError(str(message or "The issue service returned an error."))
        items = result.get("issues")
        if items is None:
            items = result.get("data")
        if items is None:
            items = result.get("items")
        if items is None:
            items = []
    else:
        raise RuntimeError("The issue service returned an unexpected response.")

    if not isinstance(items, list):
        raise RuntimeError("The issue service returned an invalid issue list.")
    return [item for item in items if isinstance(item, dict)]


def _status_chip(status: str) -> ft.Control:
    """Use the shared StatusChip when implemented, with a styled fallback."""
    builder = getattr(status_chip_component, "build_status_chip", None)
    if callable(builder):
        try:
            chip = builder(status)
            if chip is not None:
                return chip
        except Exception:
            # Do not let an unfinished shared component break the dashboard.
            pass

    label = _status_label(status)
    color, background = STATUS_COLORS.get(status, (MUTED, "#F1F0F6"))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=5),
        border_radius=20,
        bgcolor=background,
        content=ft.Text(label, size=11, color=color, weight=ft.FontWeight.BOLD),
    )


def _fallback_issue_card(
    issue: dict[str, Any],
    on_open,
) -> ft.Control:
    """Render a reusable-looking issue card until components/issue_card.py is implemented."""
    status = _normalise_status(issue)
    description = str(issue.get("description") or "No description provided.").strip()
    issue_id = issue.get("id")
    return ft.Container(
        padding=14,
        bgcolor=WHITE,
        border=ft.Border.all(1, BORDER),
        border_radius=18,
        on_click=lambda e: on_open(issue_id),
        content=ft.Row(
            [
                ft.Container(
                    width=42,
                    height=42,
                    border_radius=13,
                    bgcolor=LAVENDER,
                    alignment=ft.Alignment(0, 0),
                    content=ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=PURPLE, size=21),
                ),
                ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(
                                    _issue_title(issue),
                                    size=14,
                                    color=TEXT,
                                    weight=ft.FontWeight.BOLD,
                                    expand=True,
                                ),
                                _status_chip(status),
                            ],
                            spacing=8,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Text(description, size=12, color=MUTED, max_lines=2),
                        ft.Row(
                            [
                                ft.Icon(ft.Icons.HOME_OUTLINED, size=14, color=MUTED),
                                ft.Text(_issue_location(issue), size=11, color=MUTED, expand=True),
                                ft.Text(_issue_date(issue.get("created_at")), size=11, color=MUTED),
                            ],
                            spacing=5,
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ],
                    spacing=7,
                    expand=True,
                ),
                    ],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def _build_issue_card(issue: dict[str, Any], on_open) -> ft.Control:
    """Prefer components/issue_card.py's public builder if it exists."""
    builder = getattr(issue_card_component, "build_issue_card", None)
    if callable(builder):
        try:
            control = builder(issue, on_open)
            if control is not None:
                return control
        except Exception:
            # The component is currently a TODO; use the local fallback safely.
            pass
    return _fallback_issue_card(issue, on_open)


def view(page: ft.Page, **params) -> ft.Control:
    """Render the student home dashboard for route ``/home``."""
    state: dict[str, Any] = {
        "issues": [],
        "loading": False,
        "loaded": False,
        "error": None,
    }
    root: ft.Container | None = None

    def refresh_ui() -> None:
        if root is not None:
            root.content = _build_content()
            page.update()

    async def load_issues(e=None) -> None:
        if state["loading"]:
            return

        state["loading"] = True
        state["error"] = None
        refresh_ui()
        try:
            loader = getattr(issue_service, "list_my_issues", None)
            if not callable(loader):
                raise RuntimeError(
                    "Issue data is not connected yet. "
                    "Implement list_my_issues() in src/services/issue_service.py."
                )

            result = loader()
            if inspect.isawaitable(result):
                result = await result
            loaded_issues = _load_issue_list(result)
            # The API already sorts newest-first, but keep the dashboard correct
            # if a future service implementation returns an unsorted list.
            loaded_issues.sort(
                key=lambda item: str(item.get("created_at") or ""),
                reverse=True,
            )
            state["issues"] = loaded_issues
        except Exception as exc:
            # Keep implementation details out of the UI unless the service is missing.
            state["error"] = str(exc) if "Implement list_my_issues()" in str(exc) else (
                "We couldn't load your issues. Check your connection and try again."
            )
        finally:
            state["loading"] = False
            state["loaded"] = True
            refresh_ui()

    def start_refresh(e=None) -> None:
        page.run_task(load_issues)

    def stat_card(label: str, count: int | None, icon, tint: str, status_filter: str) -> ft.Control:
        display_count = "—" if count is None else str(count)
        return ft.Container(
            expand=True,
            padding=12,
            border_radius=18,
            bgcolor=WHITE,
            border=ft.Border.all(1, BORDER),
            on_click=lambda e: go(page, "/issues", status=status_filter),
            content=ft.Column(
                [
                    ft.Container(
                        width=34,
                        height=34,
                        border_radius=11,
                        bgcolor=tint,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(icon, color=PURPLE_DARK if tint == LAVENDER else PURPLE, size=18),
                    ),
                    ft.Text(display_count, size=23, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Text(label, size=11, color=MUTED, max_lines=1),
                ],
                spacing=7,
                tight=True,
            ),
        )

    def _empty_state() -> ft.Control:
        return ft.Container(
                padding=24,
            bgcolor=WHITE,
            border=ft.Border.all(1, BORDER),
            border_radius=20,
            content=ft.Column(
                [
                    ft.Container(
                        width=58,
                        height=58,
                        border_radius=18,
                        bgcolor=LAVENDER,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(ft.Icons.LIST_ALT_OUTLINED, color=PURPLE, size=27),
                    ),
                    ft.Text("You're all caught up", size=16, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "You haven't reported any campus issues yet. If something needs attention, let us know.",
                        size=12,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                    ft.Button(
                        "Report an issue",
                        icon=ft.Icons.ADD_ROUNDED,
                        on_click=lambda e: go(page, "/report"),
                        bgcolor=PURPLE,
                        color=WHITE,
                    ),
                ],
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _error_state() -> ft.Control:
        message = str(state.get("error") or "We couldn't load your issues. Please try again.")
        return ft.Container(
            padding=16,
            border_radius=18,
            bgcolor=ERROR_BG,
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.WIFI_OFF_ROUNDED, color=ERROR, size=23),
                    ft.Column(
                        [
                            ft.Text("Couldn't load your issues", size=14, color=ERROR, weight=ft.FontWeight.BOLD),
                            ft.Text(message, size=12, color=TEXT),
                            ft.TextButton(
                                "Try again",
                                on_click=start_refresh,
                                style=ft.ButtonStyle(color=PURPLE_DARK),
                            ),
                        ],
                        spacing=4,
                        expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ),
        )

    def _build_content() -> ft.Control:
        issues = state["issues"]
        data_ready = state["loaded"] and state["error"] is None
        counts: dict[str, int] | None = None
        if data_ready:
            counts = {
                "open": sum(1 for issue in issues if _normalise_status(issue) == "open"),
                "in_progress": sum(1 for issue in issues if _normalise_status(issue) == "in_progress"),
                "resolved": sum(1 for issue in issues if _normalise_status(issue) == "resolved"),
            }

        recent = issues[:5] if data_ready else []
        body: list[ft.Control] = [
            ft.Row(
                [
                    ft.Column(
                        [
                            ft.Text(f"Hi, {_first_name()} 👋", size=26, color=TEXT, weight=ft.FontWeight.BOLD),
                            ft.Text("Here's what's happening around your campus.", size=13, color=MUTED),
                        ],
                        spacing=5,
                        expand=True,
                    ),
                    ft.Container(
                        width=46,
                        height=46,
                        border_radius=16,
                        bgcolor=LAVENDER,
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(ft.Icons.PERSON_OUTLINE, color=PURPLE, size=24),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Container(height=8),
            ft.Container(
                padding=18,
                border_radius=22,
                bgcolor=PURPLE_DARK,
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text("Something needs fixing?", size=16, color=WHITE, weight=ft.FontWeight.BOLD),
                                ft.Text("Report it and help keep campus running smoothly.", size=12, color="#E3DEFF"),
                                ft.Button(
                                    "Report an issue",
                                    icon=ft.Icons.ADD_ROUNDED,
                                    on_click=lambda e: go(page, "/report"),
                                    bgcolor=WHITE,
                                    color=PURPLE_DARK,
                                ),
                            ],
                            spacing=9,
                            expand=True,
                        ),
                        ft.Container(
                            width=58,
                            height=58,
                            border_radius=18,
                            bgcolor="#51418F",
                            alignment=ft.Alignment(0, 0),
                            content=ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, color=WHITE, size=30),
                        ),
                    ],
                    spacing=12,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            ft.Row(
                [
                    ft.Text("Issue overview", size=17, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.Text("Tap a card to filter", size=10, color=MUTED),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            ft.Row(
                [
                    stat_card("Open", counts["open"] if counts else None, ft.Icons.ERROR_OUTLINE_ROUNDED, "#FFF4D6", "open"),
                    stat_card("In progress", counts["in_progress"] if counts else None, ft.Icons.LIST_ALT_OUTLINED, LAVENDER, "in_progress"),
                    stat_card("Resolved", counts["resolved"] if counts else None, ft.Icons.MARK_EMAIL_READ_OUTLINED, "#E5F7ED", "resolved"),
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.STRETCH,
            ),
            ft.Row(
                [
                    ft.Text("Recent issues", size=17, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Container(expand=True),
                    ft.IconButton(
                        icon=ft.Icons.REFRESH_ROUNDED,
                        tooltip="Refresh issues",
                        icon_color=PURPLE,
                        on_click=start_refresh,
                    ),
                    ft.TextButton(
                        "View all",
                        on_click=lambda e: go(page, "/issues"),
                        style=ft.ButtonStyle(color=PURPLE),
                    ),
                ],
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        ]

        if state["loading"] or not state["loaded"]:
            body.append(
                ft.Container(
                    padding=28,
                    border_radius=18,
                    bgcolor=WHITE,
                    border=ft.Border.all(1, BORDER),
                    content=ft.Column(
                        [
                            ft.ProgressRing(width=28, height=28, color=PURPLE),
                            ft.Text("Loading your issues…", size=12, color=MUTED),
                        ],
                        spacing=12,
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                )
            )
        elif state["error"]:
            body.append(_error_state())
        elif not issues:
            body.append(_empty_state())
        else:
            body.extend(
                _build_issue_card(
                    issue,
                    lambda issue_id: go(page, "/issue", id=issue_id),
                )
                for issue in recent
            )

        body.append(ft.Container(height=12))
        return ft.Column(
            body,
            spacing=14,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        )

    root = ft.Container(
        expand=True,
        bgcolor=PAGE_BG,
        padding=16,
        content=_build_content(),
    )
    # Begin loading once the page has a root control to update.
    page.run_task(load_issues)
    return root