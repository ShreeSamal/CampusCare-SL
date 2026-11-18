"""Shared building blocks for the PHO/admin screens (theme, headers, states, dialogs, contact buttons).

Pattern used by every admin screen:
    body, reload = async_body(page, load_fn, render_fn)   # shows loading -> render(data) | error + Retry
    page.run_task(reload)
"""
from datetime import datetime, timezone, timedelta

import flet as ft

from core.api_client import ApiError, NetworkError
from core.router import back

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
SUCCESS = "#1E7A43"
WARNING = "#C25A00"

IST = timezone(timedelta(hours=5, minutes=30))


# ---------------------------------------------------------
# Formatting
# ---------------------------------------------------------

def parse_dt(value) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        moment = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def fmt_dt(value, with_year: bool = False) -> str:
    moment = parse_dt(value)
    if not moment:
        return "—"
    return moment.astimezone(IST).strftime("%d %b %Y, %H:%M" if with_year else "%d %b, %H:%M")


def fmt_hours(hours) -> str:
    if hours is None:
        return "—"
    if hours < 1:
        return f"{round(hours * 60)} min"
    if hours < 48:
        return f"{hours:.1f} h"
    return f"{hours / 24:.1f} days"


def due_text(issue: dict) -> tuple[str, str]:
    """('Due in 5 h' | 'Overdue by 2 h', colour) for active complaints, ('', '') otherwise."""
    due = parse_dt(issue.get("due_at_effective") or issue.get("due_at"))
    if not due or issue.get("status") not in ("open", "assigned", "in_progress"):
        return "", ""
    hours = (due - datetime.now(timezone.utc)).total_seconds() / 3600
    if hours < 0:
        return f"Overdue by {fmt_hours(-hours)}", ERROR
    return f"Due in {fmt_hours(hours)}", WARNING if hours < 4 else MUTED


def error_text(exc: Exception) -> str:
    if isinstance(exc, NetworkError):
        return "We couldn't reach CampusCare. Check your connection and try again."
    if isinstance(exc, ApiError):
        if exc.status_code == 403:
            return "Only PHO admins can open this page."
        return exc.message
    return str(exc) or "Something went wrong."


# ---------------------------------------------------------
# Layout
# ---------------------------------------------------------

def screen(controls: list, scroll: bool = True, padding: int = 16) -> ft.Control:
    return ft.Container(
        expand=True,
        bgcolor=PAGE_BG,
        padding=ft.Padding.symmetric(horizontal=padding, vertical=14),
        content=ft.Column(controls, spacing=14, expand=True, scroll=ft.ScrollMode.AUTO if scroll else None),
    )


def page_title(title: str, subtitle: str | None = None, actions: list | None = None) -> ft.Control:
    texts = [ft.Text(title, size=24, color=TEXT, weight=ft.FontWeight.BOLD)]
    if subtitle:
        texts.append(ft.Text(subtitle, size=13, color=MUTED))
    return ft.Row(
        [ft.Column(texts, spacing=2, tight=True, expand=True), *(actions or [])],
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def back_header(page: ft.Page, title: str, subtitle: str | None = None, actions: list | None = None) -> ft.Control:
    texts = [ft.Text(title, size=19, color=TEXT, weight=ft.FontWeight.BOLD, max_lines=1,
                     overflow=ft.TextOverflow.ELLIPSIS)]
    if subtitle:
        texts.append(ft.Text(subtitle, size=12, color=MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS))
    return ft.Row(
        [
            ft.IconButton(ft.Icons.ARROW_BACK_ROUNDED, icon_color=TEXT, tooltip="Back", on_click=lambda e: back(page)),
            ft.Column(texts, spacing=0, tight=True, expand=True),
            *(actions or []),
        ],
        spacing=4,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def card(content: ft.Control, padding: int = 16, bgcolor: str = WHITE, on_click=None) -> ft.Control:
    return ft.Container(
        padding=padding,
        border_radius=18,
        bgcolor=bgcolor,
        border=ft.Border.all(1, BORDER),
        content=content,
        on_click=on_click,
        ink=on_click is not None,
    )


def section(title: str, controls: list, action: ft.Control | None = None, subtitle: str | None = None) -> ft.Control:
    head = [ft.Text(title, size=16, color=TEXT, weight=ft.FontWeight.BOLD, expand=True)]
    if action:
        head.append(action)
    items = [ft.Row(head, vertical_alignment=ft.CrossAxisAlignment.CENTER)]
    if subtitle:
        items.append(ft.Text(subtitle, size=12, color=MUTED))
    return card(ft.Column(items + controls, spacing=10, tight=True))


def info_row(icon, label: str, value: str, trailing: ft.Control | None = None) -> ft.Control:
    return ft.Row(
        [
            ft.Container(width=36, height=36, border_radius=11, bgcolor=PAGE_BG, alignment=ft.Alignment(0, 0),
                         content=ft.Icon(icon, size=18, color=PURPLE)),
            ft.Column([ft.Text(label, size=11, color=MUTED),
                       ft.Text(value or "—", size=14, color=TEXT, weight=ft.FontWeight.W_500, selectable=True)],
                      spacing=1, tight=True, expand=True),
            *([trailing] if trailing else []),
        ],
        spacing=12,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )


def pill(text: str, color: str = PURPLE_DARK, bgcolor: str = LAVENDER, icon=None) -> ft.Control:
    controls = ([ft.Icon(icon, size=13, color=color)] if icon else []) + [
        ft.Text(text, size=11, color=color, weight=ft.FontWeight.W_600)
    ]
    return ft.Container(padding=ft.Padding.symmetric(horizontal=9, vertical=4), border_radius=14, bgcolor=bgcolor,
                        content=ft.Row(controls, spacing=4, tight=True))


def primary_button(text: str, on_click=None, icon=None, expand: bool = False, danger: bool = False) -> ft.Button:
    return ft.Button(
        content=ft.Row(
            ([ft.Icon(icon, size=18, color=WHITE)] if icon else []) +
            [ft.Text(text, size=14, color=WHITE, weight=ft.FontWeight.BOLD)],
            spacing=8, tight=True, alignment=ft.MainAxisAlignment.CENTER,
        ),
        on_click=on_click,
        expand=expand or None,   # never send expand=False: Flet then stretches the child, which breaks wrap rows
        height=46,
        style=ft.ButtonStyle(bgcolor=ERROR if danger else PURPLE, color=WHITE, elevation=0,
                             shape=ft.RoundedRectangleBorder(radius=12)),
    )


def secondary_button(text: str, on_click=None, icon=None, expand: bool = False, color: str = PURPLE) -> ft.Button:
    return ft.Button(
        content=ft.Row(
            ([ft.Icon(icon, size=18, color=color)] if icon else []) +
            [ft.Text(text, size=14, color=color, weight=ft.FontWeight.W_600)],
            spacing=8, tight=True, alignment=ft.MainAxisAlignment.CENTER,
        ),
        on_click=on_click,
        expand=expand or None,   # never send expand=False: Flet then stretches the child, which breaks wrap rows
        height=46,
        style=ft.ButtonStyle(bgcolor=LAVENDER, color=color, elevation=0, shape=ft.RoundedRectangleBorder(radius=12)),
    )


def set_busy(button: ft.Button, busy: bool, text: str | None = None) -> None:
    """Disable a button and show a spinner while a request runs."""
    if busy:
        button.data = button.content
        button.content = ft.Row(
            [ft.ProgressRing(width=16, height=16, stroke_width=2, color=WHITE),
             ft.Text(text or "Saving...", size=14, color=WHITE)],
            spacing=8, tight=True, alignment=ft.MainAxisAlignment.CENTER,
        )
    elif button.data is not None:
        button.content = button.data
        button.data = None
    button.disabled = busy


def filter_chip(label: str, selected: bool, on_select) -> ft.Chip:
    return ft.Chip(
        label=ft.Text(label, size=12, color=WHITE if selected else TEXT,
                      weight=ft.FontWeight.W_600 if selected else None),
        selected=selected,
        show_checkmark=False,
        bgcolor=WHITE,
        selected_color=PURPLE,
        on_select=on_select,
    )


def dropdown(label: str, options: list[tuple[str, str]], value=None, on_select=None, width=None,
             expand: bool = False, dense: bool = True) -> ft.Dropdown:
    """options: [(key, text)]"""
    return ft.Dropdown(
        label=label,
        value=value,
        options=[ft.DropdownOption(key=str(k), text=str(t)) for k, t in options],
        on_select=on_select,
        width=width,
        expand=expand or None,   # never send expand=False: Flet then stretches the child, which breaks wrap rows
        dense=dense,
        bgcolor=WHITE,
        border_color=BORDER,
        focused_border_color=PURPLE,
        border_radius=12,
        text_style=ft.TextStyle(color=TEXT, size=13),
        label_style=ft.TextStyle(color=MUTED, size=12),
    )


def text_field(label: str, value: str = "", hint: str | None = None, multiline: bool = False, **kwargs) -> ft.TextField:
    return ft.TextField(
        label=label,
        value=value,
        hint_text=hint,
        multiline=multiline,
        min_lines=3 if multiline else None,
        max_lines=6 if multiline else 1,
        border_color=BORDER,
        focused_border_color=PURPLE,
        border_radius=12,
        bgcolor=WHITE,
        text_style=ft.TextStyle(color=TEXT, size=14),
        label_style=ft.TextStyle(color=MUTED, size=13),
        **kwargs,
    )


# ---------------------------------------------------------
# States
# ---------------------------------------------------------

def loading_view(text: str = "Loading...") -> ft.Control:
    return ft.Container(
        padding=40,
        alignment=ft.Alignment(0, 0),
        content=ft.Column([ft.ProgressRing(color=PURPLE), ft.Text(text, size=13, color=MUTED)],
                          horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=12, tight=True),
    )


def error_view(message: str, on_retry=None) -> ft.Control:
    controls = [
        ft.Icon(ft.Icons.CLOUD_OFF_ROUNDED, size=40, color=ERROR),
        ft.Text("Couldn't load this page", size=16, color=TEXT, weight=ft.FontWeight.BOLD),
        ft.Text(message, size=13, color=MUTED, text_align=ft.TextAlign.CENTER),
    ]
    if on_retry:
        controls.append(secondary_button("Retry", on_click=on_retry, icon=ft.Icons.REFRESH))
    return ft.Container(padding=32, alignment=ft.Alignment(0, 0),
                        content=ft.Column(controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                          spacing=10, tight=True))


def empty_view(icon, title: str, subtitle: str = "", action: ft.Control | None = None) -> ft.Control:
    controls = [
        ft.Container(width=64, height=64, border_radius=32, bgcolor=LAVENDER, alignment=ft.Alignment(0, 0),
                     content=ft.Icon(icon, size=30, color=PURPLE)),
        ft.Text(title, size=16, color=TEXT, weight=ft.FontWeight.BOLD, text_align=ft.TextAlign.CENTER),
    ]
    if subtitle:
        controls.append(ft.Text(subtitle, size=13, color=MUTED, text_align=ft.TextAlign.CENTER))
    if action:
        controls.append(action)
    return ft.Container(padding=28, alignment=ft.Alignment(0, 0),
                        content=ft.Column(controls, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                          spacing=10, tight=True))


def async_body(page: ft.Page, load, render, loading_text: str = "Loading...", describe_error=None):
    """Container that shows loading -> render(data) or an error with Retry. Returns (container, reload).
    describe_error(exc) -> str overrides the default error_text()."""
    describe_error = describe_error or error_text
    body = ft.Container(content=loading_view(loading_text))

    async def reload(silent: bool = False):
        if not silent:
            body.content = loading_view(loading_text)
            page.update()
        try:
            data = await load()
            body.content = render(data)
        except Exception as exc:  # noqa: BLE001 - every failure becomes a visible error state
            print("Admin screen load failed:", repr(exc))
            body.content = error_view(describe_error(exc), on_retry=lambda e: page.run_task(reload))
        page.update()

    return body, reload


# ---------------------------------------------------------
# Feedback + dialogs
# ---------------------------------------------------------

def snack(page: ft.Page, message: str, error: bool = False) -> None:
    page.show_dialog(ft.SnackBar(
        content=ft.Text(message, color=WHITE),
        bgcolor=ERROR if error else PURPLE_DARK,
        duration=3500,
    ))


def confirm_dialog(page: ft.Page, title: str, content: ft.Control | str, confirm_label: str, on_confirm,
                   danger: bool = False) -> ft.AlertDialog:
    """Modal dialog. on_confirm(dialog, button) is async; it should call page.pop_dialog() on success."""
    confirm_button = primary_button(confirm_label, danger=danger)

    async def handle_confirm(e):
        set_busy(confirm_button, True, "Please wait...")
        page.update()
        try:
            await on_confirm(dialog, confirm_button)
        finally:
            set_busy(confirm_button, False)
            page.update()

    confirm_button.on_click = handle_confirm
    dialog = ft.AlertDialog(
        modal=True,
        title=ft.Text(title, size=18, color=TEXT, weight=ft.FontWeight.BOLD),
        content=ft.Text(content, size=14, color=TEXT) if isinstance(content, str) else content,
        actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()), confirm_button],
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=WHITE,
    )
    page.show_dialog(dialog)
    return dialog


# ---------------------------------------------------------
# Contacting workers (no app accounts: phone / SMS / WhatsApp)
# ---------------------------------------------------------

def _intl(phone: str) -> str:
    digits = "".join(ch for ch in str(phone or "") if ch.isdigit())
    return digits if len(digits) > 10 else f"91{digits}"


async def open_url(page: ft.Page, url: str) -> None:
    try:
        await ft.UrlLauncher().launch_url(url)
    except Exception as exc:  # noqa: BLE001
        snack(page, f"Couldn't open {url.split(':')[0]}: {exc}", error=True)


def contact_buttons(page: ft.Page, phone: str | None, message: str | None = None) -> ft.Control:
    if not phone:
        return ft.Container()
    from urllib.parse import quote

    text = quote(message or "")
    buttons = [
        ("Call", ft.Icons.CALL, f"tel:+{_intl(phone)}"),
        ("SMS", ft.Icons.SMS_OUTLINED, f"sms:+{_intl(phone)}" + (f"?body={text}" if text else "")),
        ("WhatsApp", ft.Icons.CHAT, f"https://wa.me/{_intl(phone)}" + (f"?text={text}" if text else "")),
    ]
    return ft.Row(
        [
            ft.IconButton(icon, tooltip=label, icon_color=PURPLE, bgcolor=LAVENDER,
                          on_click=lambda e, u=url: page.run_task(open_url, page, u))
            for label, icon, url in buttons
        ],
        spacing=6,
        tight=True,
    )


def job_message(issue: dict) -> str:
    """Prefilled message to send a worker about a complaint."""
    place = issue.get("building_name") or issue.get("location_text") or "campus"
    if issue.get("room"):
        place += f", {issue['room']}"
    return (
        f"CampusCare complaint #{issue.get('id')}: {str(issue.get('category') or '').title()} at {place}. "
        f"Priority: {(issue.get('priority') or 'normal').title()}. "
        f"{(issue.get('description') or '')[:160]}"
    ).strip()