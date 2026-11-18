"""HOME  |  side: student  |  route: /home  |  navbar tab 1

- Greeting "Hi, <first name>"
- Summary cards (Open | Assigned | In progress | Resolved) - tap opens My issues with that filter
- "Report an issue" button
- "Needs your confirmation" list: issues the PHO marked resolved (confirm or reopen on the detail page)
- "Recent issues" (last 5) + "View all"
- Empty, loading and error/retry states; refresh icon

Data: issue_service.my_summary()  (GET /issues/mine/summary)
"""
from datetime import datetime

import flet as ft

from components.issue_card import build_issue_card
from core import session
from core.router import go
from screens.admin import _ui as ui
from services import issue_service

# card label, statuses counted, My issues filter label, icon, colour, background
# (one status per card so the count always equals what My issues shows for that filter)
SUMMARY_CARDS = [
    ("Open", ("open",), "Open", ft.Icons.INBOX_OUTLINED, "#5B3FD9", "#EEEAFF"),
    ("Assigned", ("assigned",), "Assigned", ft.Icons.ENGINEERING_OUTLINED, "#1F5FBF", "#E5EFFC"),
    ("In progress", ("in_progress",), "In progress", ft.Icons.CONSTRUCTION, "#9A5B00", "#FFF2DC"),
    ("Resolved", ("resolved",), "Resolved", ft.Icons.TASK_ALT, "#1E7A43", "#E3F5EA"),
]


def _greeting() -> str:
    hour = datetime.now().hour
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def view(page: ft.Page, **params) -> ft.Control:
    name = (session.user().get("name") or "").strip()
    first_name = name.split()[0] if name else "there"

    def open_issue(issue_id):
        go(page, "/issue", id=issue_id)

    def summary_card(label, statuses, filter_label, icon, color, bg, counts):
        value = sum(counts.get(s, 0) for s in statuses)
        return ft.Container(
            expand=True,
            padding=ft.Padding.symmetric(horizontal=12, vertical=14),
            border_radius=18,
            bgcolor=ui.WHITE,
            border=ft.Border.all(1, ui.BORDER),
            ink=True,
            on_click=lambda e: go(page, "/issues", status=filter_label),
            content=ft.Column(
                [
                    ft.Container(width=34, height=34, border_radius=11, bgcolor=bg, alignment=ft.Alignment(0, 0),
                                 content=ft.Icon(icon, size=18, color=color)),
                    ft.Text(str(value), size=24, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                    ft.Text(label, size=12, color=ui.MUTED, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ],
                spacing=4,
                tight=True,
            ),
        )

    def hero(data):
        active = data.get("active", 0)
        overdue = data.get("overdue", 0)
        if active:
            line = f"{active} active issue{'s' if active != 1 else ''} being handled by the PHO office."
            if overdue:
                line += f" {overdue} past the target time."
        else:
            line = "Spotted something broken on campus? Report it in under a minute."
        return ft.Container(
            padding=18,
            border_radius=22,
            gradient=ft.LinearGradient(begin=ft.Alignment(-1, -1), end=ft.Alignment(1, 1),
                                       colors=[ui.PURPLE, ui.PURPLE_DARK]),
            content=ft.Column(
                [
                    ft.Text(line, size=14, color=ui.WHITE),
                    ft.Button(
                        content=ft.Row([ft.Icon(ft.Icons.ADD_CIRCLE_OUTLINE, size=18, color=ui.PURPLE_DARK),
                                        ft.Text("Report an issue", size=14, color=ui.PURPLE_DARK,
                                                weight=ft.FontWeight.BOLD)],
                                       spacing=8, tight=True, alignment=ft.MainAxisAlignment.CENTER),
                        height=44,
                        on_click=lambda e: go(page, "/report"),
                        style=ft.ButtonStyle(bgcolor=ui.WHITE, elevation=0,
                                             shape=ft.RoundedRectangleBorder(radius=12)),
                    ),
                ],
                spacing=14,
                tight=True,
            ),
        )

    def render(data):
        counts = data.get("counts") or {}
        recent = data.get("recent") or []
        awaiting = data.get("awaiting_confirmation") or []

        controls = [
            hero(data),
            ft.Row([summary_card(*card, counts) for card in SUMMARY_CARDS[:2]], spacing=10),
            ft.Row([summary_card(*card, counts) for card in SUMMARY_CARDS[2:]], spacing=10),
        ]

        if not data.get("total"):
            controls.append(ui.card(ui.empty_view(
                ft.Icons.EMOJI_OBJECTS_OUTLINED,
                "No issues reported yet",
                "Leaking tap, flickering light, broken chair? Report it and track the fix here.",
                ui.primary_button("Report your first issue", icon=ft.Icons.ADD, on_click=lambda e: go(page, "/report")),
            )))
            return ft.Column(controls, spacing=14, tight=True)

        if awaiting:
            resolved = counts.get("resolved", len(awaiting))
            controls.append(ft.Container(
                padding=16,
                border_radius=18,
                bgcolor="#E3F5EA",
                border=ft.Border.all(1, "#BFE5CD"),
                content=ft.Column(
                    [
                        ft.Row([ft.Icon(ft.Icons.FACT_CHECK_OUTLINED, size=20, color=ui.SUCCESS),
                                ft.Text("Is it fixed?", size=16, color=ui.TEXT, weight=ft.FontWeight.BOLD,
                                        expand=True)], spacing=8),
                        ft.Text(
                            f"{resolved} issue{'s were' if resolved != 1 else ' was'} marked resolved. "
                            "Confirm the fix or reopen if the problem is still there.",
                            size=13, color=ui.TEXT,
                        ),
                        *[build_issue_card(issue, on_tap=open_issue, show_worker=False) for issue in awaiting[:3]],
                        *([ft.TextButton("See all resolved", on_click=lambda e: go(page, "/issues", status="Resolved"))]
                          if resolved > 3 else []),
                    ],
                    spacing=10,
                    tight=True,
                ),
            ))

        controls.append(ft.Row(
            [ft.Text("Recent issues", size=16, color=ui.TEXT, weight=ft.FontWeight.BOLD, expand=True),
             ft.TextButton("View all", on_click=lambda e: go(page, "/issues"))],
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ))
        controls += [build_issue_card(issue, on_tap=open_issue, show_worker=False) for issue in recent]
        return ft.Column(controls, spacing=12, tight=True)

    body, reload = ui.async_body(page, issue_service.my_summary, render, "Loading your issues...")
    page.run_task(reload)

    header = ui.page_title(
        f"Hi, {first_name}",
        f"{_greeting()} · CampusCare",
        actions=[ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", icon_color=ui.PURPLE,
                               on_click=lambda e: page.run_task(reload))],
    )
    return ui.screen([header, body])