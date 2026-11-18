"""ISSUE CARD - one complaint row in lists (admin complaints, dashboard, worker jobs).

build_issue_card(issue, on_tap, show_worker=True, leading=None, on_assign_suggested=None)
  issue: a row from the admin API (_issue_view): id, category, description, building_name, room,
         status, priority, worker {id, name} | None, created_at, overdue,
         suggestion {worker {id, name}, score, eligible, reasons} | None  (unassigned open rows only)
  on_tap(issue_id) is called when the card is tapped. `leading` (e.g. a Checkbox) is shown on the left.
  on_assign_suggested(issue_id, worker_id) -> shows "Suggested: <name>" + an Assign button (admin lists).
"""
from datetime import datetime, timezone

import flet as ft

from components.status_chip import build_overdue_badge, build_priority_badge, build_status_chip

CATEGORY_ICONS = {
    "plumbing": ft.Icons.WATER_DROP_OUTLINED,
    "electrical": ft.Icons.BOLT,
    "civil": ft.Icons.CONSTRUCTION,
    "housekeeping": ft.Icons.CLEANING_SERVICES_OUTLINED,
    "network": ft.Icons.WIFI,
    "furniture": ft.Icons.CHAIR_OUTLINED,
    "lighting": ft.Icons.LIGHTBULB_OUTLINE,
    "other": ft.Icons.REPORT_PROBLEM_OUTLINED,
}

TEXT = "#211B36"
MUTED = "#77728C"
BORDER = "#E8E4F3"
PURPLE = "#7054F6"
LAVENDER = "#F0EDFF"


def time_ago(value) -> str:
    if not value:
        return ""
    try:
        moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    seconds = (datetime.now(timezone.utc) - moment).total_seconds()
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{int(seconds // 60)}m ago"
    if seconds < 86400:
        return f"{int(seconds // 3600)}h ago"
    if seconds < 86400 * 30:
        return f"{int(seconds // 86400)}d ago"
    return moment.strftime("%d %b %Y")


def _suggestion_row(issue: dict, on_assign_suggested) -> ft.Control | None:
    suggestion = issue.get("suggestion") or {}
    worker = suggestion.get("worker") or {}
    if not worker.get("id"):
        return None
    eligible = suggestion.get("eligible", True)
    label = [
        ft.Icon(ft.Icons.AUTO_AWESOME, size=14, color=PURPLE),
        ft.Text("Suggested:", size=11, color=MUTED),
        ft.Text(worker.get("name") or "Worker", size=12, color=TEXT, weight=ft.FontWeight.BOLD,
                max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
        ft.Text(f"· {suggestion.get('score', 0)}", size=11, color=MUTED),
    ]
    if not eligible:
        label.append(ft.Text("(fallback)", size=11, color="#C25A00", weight=ft.FontWeight.W_600))
    reasons = suggestion.get("reasons") or []
    return ft.Container(
        padding=ft.Padding.only(left=10, right=4, top=4, bottom=4),
        border_radius=12,
        bgcolor=LAVENDER,
        tooltip=" · ".join(reasons) or None,
        content=ft.Row(
            [
                ft.Row(label, spacing=4, expand=True, vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ft.TextButton(
                    "Assign",
                    icon=ft.Icons.PERSON_ADD_ALT_1_OUTLINED,
                    on_click=lambda e: on_assign_suggested(issue.get("id"), worker["id"]),
                    style=ft.ButtonStyle(color=PURPLE),
                ),
            ],
            spacing=4,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
    )


def build_issue_card(issue: dict, on_tap=None, show_worker: bool = True, leading: ft.Control | None = None,
                     on_assign_suggested=None) -> ft.Control:
    category = str(issue.get("category") or "other").lower()
    place = issue.get("building_name") or issue.get("location_text") or "Location not given"
    if issue.get("room"):
        place = f"{place} · {issue['room']}"

    badges = [build_status_chip(issue.get("status"))]
    priority = build_priority_badge(issue.get("priority"), hide_normal=True)
    if priority:
        badges.append(priority)
    if issue.get("overdue"):
        badges.append(build_overdue_badge())

    footer = [ft.Icon(ft.Icons.SCHEDULE, size=13, color=MUTED), ft.Text(time_ago(issue.get("created_at")), size=11, color=MUTED)]
    if show_worker:
        worker = issue.get("worker") or {}
        footer += [
            ft.Container(width=8),
            ft.Icon(ft.Icons.ENGINEERING_OUTLINED, size=14, color=PURPLE if worker else MUTED),
            ft.Text(
                worker.get("name") or "Unassigned",
                size=11,
                color=TEXT if worker else MUTED,
                weight=ft.FontWeight.W_600 if worker else None,
                italic=not worker,
            ),
        ]

    suggestion_row = _suggestion_row(issue, on_assign_suggested) if on_assign_suggested else None
    body = ft.Column(
        [
            ft.Row(
                [
                    ft.Text(f"#{issue.get('id')}", size=12, color=MUTED, weight=ft.FontWeight.BOLD),
                    ft.Text(category.title(), size=14, color=TEXT, weight=ft.FontWeight.BOLD, expand=True,
                            max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ],
                spacing=6,
            ),
            ft.Text(issue.get("description") or "No description", size=13, color=TEXT, max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS),
            ft.Row([ft.Icon(ft.Icons.PLACE_OUTLINED, size=13, color=MUTED),
                    ft.Text(place, size=11, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS, expand=True)],
                   spacing=4),
            ft.Row(badges, spacing=6, wrap=True, run_spacing=6),
            ft.Row(footer, spacing=4, vertical_alignment=ft.CrossAxisAlignment.CENTER),
            *([suggestion_row] if suggestion_row else []),
        ],
        spacing=6,
        tight=True,
        expand=True,
    )

    icon = ft.Container(
        width=40,
        height=40,
        border_radius=12,
        bgcolor=LAVENDER,
        alignment=ft.Alignment(0, 0),
        content=ft.Icon(CATEGORY_ICONS.get(category, ft.Icons.REPORT_PROBLEM_OUTLINED), size=20, color=PURPLE),
    )

    row = [leading] if leading is not None else []
    row += [icon, body]
    return ft.Container(
        padding=14,
        border_radius=16,
        bgcolor="#FFFFFF",
        border=ft.Border.all(1, "#F3C6D3" if issue.get("overdue") else BORDER),
        ink=True,
        on_click=(lambda e: on_tap(issue.get("id"))) if on_tap else None,
        content=ft.Row(row, spacing=12, vertical_alignment=ft.CrossAxisAlignment.START),
    )