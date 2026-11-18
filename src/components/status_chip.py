"""STATUS CHIP + PRIORITY BADGE - coloured pills. Single source of status / priority colours.

Status values are identical to the backend (issues_status_check / ALLOWED_TRANSITIONS in backend/routers/admin.py):
open, assigned, in_progress, resolved, closed, rejected.
"""
import flet as ft

# status -> (label, text colour, background)
STATUS_STYLE = {
    "open": ("Open", "#5B3FD9", "#EEEAFF"),
    "assigned": ("Assigned", "#1F5FBF", "#E5EFFC"),
    "in_progress": ("In progress", "#9A5B00", "#FFF2DC"),
    "resolved": ("Resolved", "#1E7A43", "#E3F5EA"),
    "closed": ("Closed", "#5F5A6B", "#EFEEF2"),
    "rejected": ("Rejected", "#B4234D", "#FDE8EE"),
}

# priority -> (label, text colour, background, icon)
PRIORITY_STYLE = {
    "urgent": ("Urgent", "#FFFFFF", "#C62848", ft.Icons.PRIORITY_HIGH),
    "high": ("High", "#B4234D", "#FDE8EE", ft.Icons.KEYBOARD_DOUBLE_ARROW_UP),
    "normal": ("Normal", "#5F5A6B", "#EFEEF2", ft.Icons.REMOVE),
    "low": ("Low", "#1F5FBF", "#E5EFFC", ft.Icons.KEYBOARD_ARROW_DOWN),
}


def status_label(status: str | None) -> str:
    key = (status or "open").strip().lower().replace(" ", "_")
    return STATUS_STYLE.get(key, (key.replace("_", " ").title(), "", ""))[0]


def _pill(text: str, color: str, bgcolor: str, icon=None, size: int = 11) -> ft.Control:
    controls = []
    if icon:
        controls.append(ft.Icon(icon, size=size + 2, color=color))
    controls.append(ft.Text(text, size=size, color=color, weight=ft.FontWeight.BOLD))
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=9, vertical=4),
        border_radius=20,
        bgcolor=bgcolor,
        content=ft.Row(controls, spacing=4, tight=True),
    )


def build_status_chip(status: str | None, size: int = 11) -> ft.Control:
    key = (status or "open").strip().lower().replace(" ", "_")
    label, color, bg = STATUS_STYLE.get(key, (key.replace("_", " ").title(), "#5F5A6B", "#EFEEF2"))
    return _pill(label, color, bg, size=size)


def build_priority_badge(priority: str | None, size: int = 11, hide_normal: bool = False) -> ft.Control | None:
    key = (priority or "normal").lower()
    if hide_normal and key == "normal":
        return None
    label, color, bg, icon = PRIORITY_STYLE.get(key, PRIORITY_STYLE["normal"])
    return _pill(label, color, bg, icon=icon, size=size)


def build_overdue_badge(size: int = 11) -> ft.Control:
    return _pill("Overdue", "#FFFFFF", "#B4234D", icon=ft.Icons.SCHEDULE, size=size)