"""PROFILE  |  side: shared  |  route: /profile  |  navbar tab 4

UI TODO
  [ ] Avatar circle with initials
  [ ] Name, institute email, roll number, hostel/building (read-only to start)
  [ ] Role badge (Student / Staff)
  [ ] (later) Edit profile (name, hostel) and Change password
  [ ] (later) Notification preferences switch
  [ ] App version text
  [ ] Button "Log out" with a confirm dialog
  [ ] No charts on this screen

Behaviour TODO
  [ ] Logout: auth_service.logout(refresh_token) -> session.clear() (also remove stored token) -> reset(page, "/login")
"""

"""PROFILE | shared screen | route: /profile | navbar tab 4

Displays read-only account information from the in-memory session.
Profile editing, password changes, notification preferences, persistent token
removal, and server-side logout can be added when their services are available.
"""

import inspect

import flet as ft

from core import session
from core.router import reset
from services import auth_service

# Keep these colours aligned with the authentication screens.
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
APP_VERSION = "0.1.0"  # Keep aligned with pyproject.toml.


def _first_nonempty(*values, default: str = "Not provided") -> str:
    """Return the first useful value as display text."""
    for value in values:
        if value is not None and str(value).strip():
            return str(value).strip()
    return default


def _initials(name: str) -> str:
    """Build a 1–2 letter avatar label from a user's display name."""
    words = [part for part in name.strip().split() if part]
    if not words:
        return "CC"
    if len(words) == 1:
        return words[0][:1].upper()
    return f"{words[0][0]}{words[-1][0]}".upper()


def _detail_row(icon, label: str, value: str) -> ft.Control:
    return ft.Row(
        controls=[
            ft.Container(
                width=42,
                height=42,
                border_radius=13,
                bgcolor=PAGE_BG,
                alignment=ft.Alignment(0, 0),
                content=ft.Icon(icon, color=PURPLE, size=20),
            ),
            ft.Column(
                controls=[
                    ft.Text(label, size=12, color=MUTED),
                    ft.Text(
                        value,
                        size=14,
                        color=TEXT,
                        weight=ft.FontWeight.W_500,
                        max_lines=2,
                    ),
                ],
                spacing=3,
                tight=True,
                expand=True,
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def _separator() -> ft.Control:
    return ft.Container(height=1, bgcolor=BORDER)


def view(page: ft.Page, **params) -> ft.Control:
    user = session.user() or {}
    metadata = user.get("user_metadata") or user.get("metadata") or {}

    full_name = _first_nonempty(
        user.get("name"),
        user.get("full_name"),
        metadata.get("full_name"),
        default="CampusCare user",
    )
    email = _first_nonempty(user.get("email"), metadata.get("email"))
    roll_number = _first_nonempty(
        user.get("roll_number"),
        user.get("roll_no"),
        user.get("roll"),
        metadata.get("roll_number"),
        metadata.get("roll_no"),
    )
    building = _first_nonempty(
        user.get("building_name"),
        user.get("hostel"),
        user.get("building"),
        user.get("building_id"),
        metadata.get("building_name"),
        metadata.get("hostel"),
        metadata.get("building"),
        metadata.get("building_id"),
    )

    raw_role = str(user.get("role") or metadata.get("role") or "student").strip().lower()
    is_staff = raw_role in {"staff", "admin", "maintenance", "support"}
    role_label = "Staff" if is_staff else "Student"
    role_bg = "#F0ECFF" if is_staff else "#EAF7F0"
    role_color = PURPLE_DARK if is_staff else "#23764B"

    viewport_width = getattr(page, "width", None)
    compact = viewport_width is None or viewport_width < 560
    content_width = max(180, int((viewport_width or 390) - 36))

    avatar = ft.Container(
        width=88,
        height=88,
        border_radius=44,
        bgcolor=LAVENDER,
        alignment=ft.Alignment(0, 0),
        content=ft.Text(
            _initials(full_name),
            size=28,
            color=PURPLE_DARK,
            weight=ft.FontWeight.BOLD,
        ),
    )

    role_badge = ft.Container(
        padding=ft.Padding.symmetric(horizontal=11, vertical=6),
        border_radius=24,
        bgcolor=role_bg,
        content=ft.Row(
            controls=[
                ft.Icon(
                    ft.Icons.BADGE_OUTLINED if hasattr(ft.Icons, "BADGE_OUTLINED") else ft.Icons.PERSON_OUTLINE,
                    size=15,
                    color=role_color,
                ),
                ft.Text(role_label, size=12, weight=ft.FontWeight.BOLD, color=role_color),
            ],
            spacing=6,
            tight=True,
        ),
    )

    identity_text = ft.Column(
        controls=[
            ft.Text(
                full_name,
                size=22 if compact else 24,
                color=TEXT,
                weight=ft.FontWeight.BOLD,
                text_align=ft.TextAlign.CENTER if compact else ft.TextAlign.LEFT,
                max_lines=2,
            ),
            ft.Text(
                email,
                size=13,
                color=MUTED,
                text_align=ft.TextAlign.CENTER if compact else ft.TextAlign.LEFT,
                max_lines=2,
            ),
            role_badge,
        ],
        spacing=8,
        horizontal_alignment=(ft.CrossAxisAlignment.CENTER if compact else ft.CrossAxisAlignment.START),
        tight=True,
    )

    if compact:
        identity_content = ft.Column(
            controls=[avatar, identity_text],
            spacing=14,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            tight=True,
        )
    else:
        identity_content = ft.Row(
            controls=[avatar, identity_text],
            spacing=20,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    identity_card = ft.Container(
        width=content_width,
        padding=22,
        border_radius=22,
        bgcolor=WHITE,
        content=identity_content,
    )

    details_card = ft.Container(
        width=content_width,
        padding=20,
        border_radius=22,
        bgcolor=WHITE,
        content=ft.Column(
            controls=[
                ft.Text("Account details", size=17, color=TEXT, weight=ft.FontWeight.BOLD),
                ft.Text("Your registered campus information", size=12, color=MUTED),
                ft.Container(height=4),
                _detail_row(ft.Icons.PERSON_OUTLINE, "Full name", full_name),
                _separator(),
                _detail_row(ft.Icons.MAIL_OUTLINE_ROUNDED, "Institute email", email),
                _separator(),
                _detail_row(ft.Icons.BADGE_OUTLINED if hasattr(ft.Icons, "BADGE_OUTLINED") else ft.Icons.INFO_OUTLINE, "Roll number", roll_number),
                _separator(),
                _detail_row(ft.Icons.HOME_OUTLINED, "Hostel / building", building),
            ],
            spacing=14,
            tight=True,
        ),
    )

    # The current repository's auth_service.py has no logout() endpoint yet.
    # This capability check allows server logout to be used once implemented,
    # while always clearing the current in-memory session locally.
    async def confirm_logout(e) -> None:
        page.pop_dialog()
        logout_fn = getattr(auth_service, "logout", None)
        refresh_token = session.refresh_token()
        try:
            if callable(logout_fn):
                result = logout_fn(refresh_token)
                if inspect.isawaitable(result):
                    await result
        except Exception:
            # Do not keep the local session active if server logout is unavailable.
            pass
        finally:
            # session.clear() currently clears in-memory tokens only; the current
            # session implementation does not persist tokens to local storage.
            session.clear()
            reset(page, "/login")

    def cancel_logout(e) -> None:
        page.pop_dialog()

    logout_dialog = ft.AlertDialog(
        modal=True,
        bgcolor=WHITE,
        title=ft.Text("Log out of CampusCare?", color=TEXT, weight=ft.FontWeight.BOLD, size=19),
        content=ft.Text(
            "You'll need to sign in again to access your campus account.",
            color=MUTED,
            size=14,
        ),
        actions=[
            ft.TextButton(
                content="Cancel",
                on_click=cancel_logout,
                style=ft.ButtonStyle(color=PURPLE),
            ),
            ft.Button(
                content="Log out",
                icon=ft.Icons.LOGOUT,
                on_click=confirm_logout,
                style=ft.ButtonStyle(bgcolor=ERROR, color=WHITE),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=20),
    )

    def ask_logout(e) -> None:
        page.show_dialog(logout_dialog)

    logout_summary = ft.Row(
        controls=[
            ft.Container(
                width=42,
                height=42,
                border_radius=13,
                bgcolor=ERROR_BG,
                alignment=ft.Alignment(0, 0),
                content=ft.Icon(ft.Icons.LOGOUT, color=ERROR, size=20),
            ),
            ft.Column(
                controls=[
                    ft.Text("Sign out", size=15, color=TEXT, weight=ft.FontWeight.BOLD),
                    ft.Text(
                        "Log out of your current account on this device.",
                        size=12,
                        color=MUTED,
                        max_lines=2,
                    ),
                ],
                spacing=4,
                tight=True,
                expand=True,
            ),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )
    logout_button = ft.Button(
        content="Log out",
        on_click=ask_logout,
        style=ft.ButtonStyle(bgcolor=ERROR_BG, color=ERROR),
    )
    logout_card_content = (
        ft.Column(
            controls=[
                logout_summary,
                ft.Row([logout_button], alignment=ft.MainAxisAlignment.END),
            ],
            spacing=14,
            tight=True,
        )
        if compact
        else ft.Row(
            controls=[logout_summary, logout_button],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
    )
    logout_card = ft.Container(
        width=content_width,
        padding=18,
        border_radius=20,
        bgcolor=WHITE,
        content=logout_card_content,
    )

    return ft.Container(
        expand=True,
        bgcolor=PAGE_BG,
        padding=ft.Padding.symmetric(horizontal=18, vertical=20),
        content=ft.Column(
            controls=[
                ft.Column(
                    controls=[
                        ft.Text("Profile", size=27, color=TEXT, weight=ft.FontWeight.BOLD),
                        ft.Text("Your account and campus details", size=13, color=MUTED),
                    ],
                    spacing=4,
                    tight=True,
                ),
                identity_card,
                details_card,
                logout_card,
                ft.Container(
                    padding=ft.Padding.symmetric(vertical=6),
                    alignment=ft.Alignment(0, 0),
                    content=ft.Text(
                        f"CampusCare  •  v{APP_VERSION}",
                        size=11,
                        color=MUTED,
                        text_align=ft.TextAlign.CENTER,
                    ),
                ),
            ],
            spacing=16,
            scroll=ft.ScrollMode.AUTO,
            expand=True,
        ),
    )