"""ISSUE DETAIL  |  side: student (staff use /admin/complaint)  |  route: /issue  |  navbar: hidden
Param: id (issue id), e.g. go(page, "/issue", id=42). Shows a back button instead of the navbar.

  - Header: category, status chip, priority badge, overdue badge, reported date, SLA due text
  - "Is it fixed?" action card when the PHO marked it resolved:
        Confirm & close (1-5 star rating + optional feedback)  |  Reopen (reason required)
  - Progress stepper: Reported -> Assigned -> In progress -> Resolved -> Closed (or Rejected)
  - Photos (tap to zoom), description, location (building, room, GPS -> open in maps)
  - Assigned worker: name + call / SMS / WhatsApp
  - Timeline of status events (actor = You / PHO office; admin internal notes are never sent)
  - Comments: list + "Add a comment" (closed for closed / rejected issues)
  - Your feedback (after closing)

Staff: NOT handled here. The PHO/admin view is screens/admin/complaint_detail.py (/admin/complaint).
Data: issue_service.get_issue, add_comment, confirm, reopen
"""
import flet as ft

from components.issue_card import CATEGORY_ICONS
from components.status_chip import build_overdue_badge, build_priority_badge, build_status_chip, status_label
from core.api_client import ApiError
from screens.admin import _ui as ui
from services import issue_service

EVENT_TEXT = {
    "created": ("You reported this issue", ft.Icons.FLAG_OUTLINED),
    "status_changed": ("Status changed", ft.Icons.SYNC_ALT),
    "assigned": ("Worker assigned", ft.Icons.ENGINEERING_OUTLINED),
    "reassigned": ("Worker changed", ft.Icons.SWAP_HORIZ),
    "unassigned": ("Back in the queue", ft.Icons.PERSON_REMOVE_OUTLINED),
    "reopened": ("Reopened", ft.Icons.REPLAY),
}

STATUS_TEXT = {
    "open": "Waiting for the PHO office to assign a worker.",
    "assigned": "A worker has been assigned and will visit soon.",
    "in_progress": "Work is in progress.",
    "resolved": "The PHO office marked this as fixed. Please confirm or reopen.",
    "closed": "This issue is closed.",
    "rejected": "The PHO office could not take this issue up.",
}

STEPS = [("open", "Reported"), ("assigned", "Assigned"), ("in_progress", "In progress"),
         ("resolved", "Resolved"), ("closed", "Closed")]

STAR = "#F2A900"


def _api_message(exc: Exception) -> str:
    if isinstance(exc, ApiError) and exc.status_code == 404:
        return "This issue doesn't exist or isn't yours."
    return ui.error_text(exc)


def view(page: ft.Page, id: int | None = None, **params) -> ft.Control:
    issue_id = id

    async def load():
        if issue_id is None:
            raise ValueError("No issue selected.")
        return await issue_service.get_issue(issue_id)

    def render(data):
        issue = data.get("issue") or {}
        controls = [header_card(issue)]
        if data.get("can_confirm") or data.get("can_reopen"):
            controls.append(action_card(data))
        controls.append(progress_card(issue, data.get("timeline") or []))
        if data.get("feedback"):
            controls.append(feedback_card(data["feedback"]))
        if issue.get("photo_urls"):
            controls.append(photos_card(issue["photo_urls"]))
        controls.append(details_card(issue))
        if issue.get("worker"):
            controls.append(worker_card(issue))
        controls.append(timeline_card(data.get("timeline") or []))
        controls.append(comments_card(data.get("comments") or [], data.get("can_comment")))
        return ft.Column(controls, spacing=14, tight=True)

    body, reload = ui.async_body(page, load, render, "Loading issue...", describe_error=_api_message)

    # ---------------------------------------------------------
    # Cards
    # ---------------------------------------------------------

    def header_card(issue):
        category = str(issue.get("category") or "other").lower()
        badges = [build_status_chip(issue.get("status"), size=12)]
        priority = build_priority_badge(issue.get("priority"), size=12, hide_normal=True)
        if priority:
            badges.append(priority)
        if issue.get("overdue"):
            badges.append(build_overdue_badge(size=12))

        lines = [ft.Row([ft.Icon(ft.Icons.SCHEDULE, size=14, color=ui.MUTED),
                         ft.Text(f"Reported {ui.fmt_dt(issue.get('created_at'), with_year=True)}", size=12,
                                 color=ui.MUTED)], spacing=4)]
        due, due_color = ui.due_text(issue)
        if due:
            lines.append(ft.Row([ft.Icon(ft.Icons.TIMER_OUTLINED, size=14, color=due_color),
                                 ft.Text(f"Target: {due}", size=12, color=due_color, weight=ft.FontWeight.W_600)],
                                spacing=4))
        if issue.get("closed_at"):
            lines.append(ft.Text(f"Closed {ui.fmt_dt(issue['closed_at'], with_year=True)}", size=12, color=ui.MUTED))
        elif issue.get("resolved_at"):
            lines.append(ft.Text(f"Resolved {ui.fmt_dt(issue['resolved_at'], with_year=True)}", size=12,
                                 color=ui.MUTED))

        return ui.card(ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(width=52, height=52, border_radius=16, bgcolor=ui.LAVENDER,
                                     alignment=ft.Alignment(0, 0),
                                     content=ft.Icon(CATEGORY_ICONS.get(category, ft.Icons.REPORT_PROBLEM_OUTLINED),
                                                     size=26, color=ui.PURPLE)),
                        ft.Column(
                            [ft.Text(category.title(), size=20, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                             ft.Row(badges, spacing=6, wrap=True, run_spacing=6)],
                            spacing=6, tight=True, expand=True,
                        ),
                    ],
                    spacing=14,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
                *lines,
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                    border_radius=12,
                    bgcolor=ui.PAGE_BG,
                    content=ft.Text(STATUS_TEXT.get(issue.get("status"), ""), size=13, color=ui.TEXT),
                ),
            ],
            spacing=8,
            tight=True,
        ))

    def action_card(data):
        buttons = []
        if data.get("can_confirm"):
            buttons.append(ui.primary_button("Yes, it's fixed", icon=ft.Icons.CHECK_CIRCLE_OUTLINE, expand=True,
                                             on_click=lambda e: open_confirm_dialog()))
        if data.get("can_reopen"):
            buttons.append(ui.secondary_button("Still broken", icon=ft.Icons.REPLAY, expand=True, color=ui.ERROR,
                                               on_click=lambda e: open_reopen_dialog()))
        return ft.Container(
            padding=16,
            border_radius=18,
            bgcolor="#E3F5EA",
            border=ft.Border.all(1, "#BFE5CD"),
            content=ft.Column(
                [
                    ft.Row([ft.Icon(ft.Icons.FACT_CHECK_OUTLINED, size=20, color=ui.SUCCESS),
                            ft.Text("Is the problem fixed?", size=16, color=ui.TEXT, weight=ft.FontWeight.BOLD)],
                           spacing=8),
                    ft.Text("Confirming closes the issue. If it's still not working, reopen it and tell us what's wrong.",
                            size=13, color=ui.TEXT),
                    ft.Row(buttons, spacing=10),
                ],
                spacing=10,
                tight=True,
            ),
        )

    def progress_card(issue, timeline):
        status = issue.get("status") or "open"
        if status == "rejected":
            reason = next((e.get("note") for e in reversed(timeline)
                           if e.get("to_status") == "rejected" and e.get("note")), None)
            return ft.Container(
                padding=16, border_radius=18, bgcolor=ui.ERROR_BG, border=ft.Border.all(1, "#F3C6D3"),
                content=ft.Column(
                    [ft.Row([ft.Icon(ft.Icons.BLOCK, size=20, color=ui.ERROR),
                             ft.Text("Rejected", size=16, color=ui.ERROR, weight=ft.FontWeight.BOLD)], spacing=8),
                     ft.Text(f"Reason: {reason}" if reason else "No reason was given.", size=13, color=ui.TEXT)],
                    spacing=8, tight=True,
                ),
            )

        keys = [k for k, _ in STEPS]
        current = keys.index(status) if status in keys else 0
        cells = []
        for index, (key, label) in enumerate(STEPS):
            done = index < current
            active = index == current
            color = ui.PURPLE if (done or active) else ui.BORDER
            cells.append(ft.Column(
                [
                    ft.Container(
                        width=26, height=26, border_radius=13,
                        bgcolor=color if (done or active) else ui.WHITE,
                        border=ft.Border.all(2, color),
                        alignment=ft.Alignment(0, 0),
                        content=ft.Icon(ft.Icons.CHECK if done else ft.Icons.CIRCLE, size=13 if done else 8,
                                        color=ui.WHITE if (done or active) else ui.BORDER),
                    ),
                    ft.Text(label, size=10, color=ui.TEXT if (done or active) else ui.MUTED,
                            weight=ft.FontWeight.BOLD if active else None, text_align=ft.TextAlign.CENTER),
                ],
                spacing=4, tight=True, expand=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ))
            if index < len(STEPS) - 1:
                cells.append(ft.Container(height=2, width=14, margin=ft.Margin.only(bottom=18),
                                          bgcolor=ui.PURPLE if index < current else ui.BORDER))
        return ui.section("Progress", [ft.Row(cells, spacing=0, vertical_alignment=ft.CrossAxisAlignment.CENTER)])

    def feedback_card(feedback):
        rating = feedback.get("rating") or 0
        stars = [ft.Icon(ft.Icons.STAR_ROUNDED if i < rating else ft.Icons.STAR_OUTLINE_ROUNDED, size=22, color=STAR)
                 for i in range(5)]
        items = [ft.Row(stars + [ft.Text(f"{rating}/5", size=13, color=ui.MUTED)], spacing=2)]
        if feedback.get("text"):
            items.append(ft.Text(feedback["text"], size=13, color=ui.TEXT))
        items.append(ft.Text(ui.fmt_dt(feedback.get("created_at"), with_year=True), size=11, color=ui.MUTED))
        return ui.section("Your feedback", items)

    def photos_card(urls):
        def zoom(url):
            page.show_dialog(ft.AlertDialog(
                content=ft.InteractiveViewer(
                    content=ft.Image(src=url, fit=ft.BoxFit.CONTAIN, width=600, height=600), max_scale=5,
                ),
                actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog())],
                bgcolor=ui.WHITE,
            ))

        return ui.section("Photos", [ft.Row(
            [
                ft.Container(
                    width=120, height=120, border_radius=14, clip_behavior=ft.ClipBehavior.HARD_EDGE,
                    on_click=lambda e, u=url: zoom(u), ink=True,
                    content=ft.Image(src=url, fit=ft.BoxFit.COVER, width=120, height=120,
                                     error_content=ft.Icon(ft.Icons.BROKEN_IMAGE_OUTLINED, color=ui.MUTED)),
                )
                for url in urls
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )], subtitle="Tap a photo to zoom")

    def details_card(issue):
        place = issue.get("building_name") or issue.get("location_text") or "Not given"
        rows = [
            ft.Text(issue.get("description") or "No description", size=14, color=ui.TEXT, selectable=True),
            ft.Divider(height=1, color=ui.BORDER),
            ui.info_row(ft.Icons.APARTMENT_OUTLINED, "Building", place),
        ]
        if issue.get("room"):
            rows.append(ui.info_row(ft.Icons.MEETING_ROOM_OUTLINED, "Room / spot", issue["room"]))
        if issue.get("location_text") and issue.get("location_text") != place:
            rows.append(ui.info_row(ft.Icons.NOTES, "Location note", issue["location_text"]))
        if issue.get("latitude") is not None and issue.get("longitude") is not None:
            url = f"https://www.google.com/maps/search/?api=1&query={issue['latitude']},{issue['longitude']}"
            rows.append(ui.info_row(
                ft.Icons.MY_LOCATION, "GPS", f"{issue['latitude']:.5f}, {issue['longitude']:.5f}",
                trailing=ft.TextButton("Open in maps", on_click=lambda e: page.run_task(ui.open_url, page, url)),
            ))
        return ui.section("Details", rows)

    def worker_card(issue):
        worker = issue["worker"]
        subtitle = f"Assigned {ui.fmt_dt(worker['assigned_at'])}" if worker.get("assigned_at") else None
        skill = str(worker.get("primary_skill") or "").title()
        return ui.section(
            "Assigned to",
            [ui.info_row(
                ft.Icons.ENGINEERING_OUTLINED,
                skill or "Worker",
                worker.get("name") or "PHO worker",
                trailing=ui.contact_buttons(
                    page, worker.get("phone"),
                    f"Hi, this is about CampusCare issue #{issue.get('id')} "
                    f"({str(issue.get('category') or '').title()}).",
                ),
            )],
            subtitle=subtitle,
        )

    def timeline_card(events):
        rows = []
        for index, event in enumerate(events):
            title, icon = EVENT_TEXT.get(event.get("type"), (str(event.get("type") or "").replace("_", " ").title(),
                                                             ft.Icons.CIRCLE_OUTLINED))
            if event.get("type") == "status_changed" and event.get("to_status"):
                title = f"{status_label(event.get('from_status'))} → {status_label(event['to_status'])}"
            last = index == len(events) - 1
            rows.append(ft.Row(
                [
                    ft.Column(
                        [ft.Container(width=30, height=30, border_radius=15,
                                      bgcolor=ui.PURPLE if last else ui.LAVENDER, alignment=ft.Alignment(0, 0),
                                      content=ft.Icon(icon, size=15, color=ui.WHITE if last else ui.PURPLE)),
                         ft.Container(width=2, height=26, bgcolor=ui.BORDER, visible=not last)],
                        spacing=0, tight=True, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Column(
                        [ft.Text(title, size=13, color=ui.TEXT, weight=ft.FontWeight.BOLD),
                         ft.Text(f"{event.get('actor') or ''} · {ui.fmt_dt(event.get('created_at'))}", size=11,
                                 color=ui.MUTED),
                         *([ft.Text(event["note"], size=12, color=ui.TEXT)] if event.get("note") else [])],
                        spacing=2, tight=True, expand=True,
                    ),
                ],
                spacing=12,
                vertical_alignment=ft.CrossAxisAlignment.START,
            ))
        return ui.section("Timeline", rows or [ft.Text("No updates yet.", size=13, color=ui.MUTED)])

    def comments_card(comments, can_comment):
        items = []
        for c in comments:
            mine = c.get("mine")
            items.append(ft.Row(
                [ft.Container(
                    padding=ft.Padding.symmetric(horizontal=12, vertical=9),
                    border_radius=14,
                    bgcolor=ui.LAVENDER if mine else ui.PAGE_BG,
                    content=ft.Column(
                        [ft.Text(f"{c.get('author') or ''} · {ui.fmt_dt(c.get('created_at'))}", size=11,
                                 color=ui.MUTED),
                         ft.Text(c.get("text") or "", size=13, color=ui.TEXT, selectable=True)],
                        spacing=2, tight=True,
                    ),
                    expand=True,
                )],
                alignment=ft.MainAxisAlignment.END if mine else ft.MainAxisAlignment.START,
            ))
        if not items:
            items.append(ft.Text("No comments yet. Add details that might help the worker "
                                 "(e.g. when you're in the room).", size=13, color=ui.MUTED))

        if can_comment:
            field = ui.text_field("Add a comment", hint="Visible to the PHO office", multiline=True, max_length=1000)
            send = ui.primary_button("Send", icon=ft.Icons.SEND_ROUNDED)

            async def submit(e):
                text = (field.value or "").strip()
                if not text:
                    field.error = "Write something first."
                    page.update()
                    return
                ui.set_busy(send, True, "Sending...")
                page.update()
                try:
                    await issue_service.add_comment(issue_id, text)
                except Exception as exc:  # noqa: BLE001
                    ui.set_busy(send, False)
                    ui.snack(page, _api_message(exc), error=True)
                    page.update()
                    return
                ui.snack(page, "Comment added.")
                await reload(silent=True)

            def clear_error(e):
                if field.error:
                    field.error = None
                    page.update()

            send.on_click = submit
            field.on_change = clear_error
            items += [field, ft.Row([send], alignment=ft.MainAxisAlignment.END)]
        else:
            items.append(ft.Text("Comments are closed for this issue.", size=12, color=ui.MUTED, italic=True))
        return ui.section("Comments", items)

    # ---------------------------------------------------------
    # Dialogs
    # ---------------------------------------------------------

    def open_confirm_dialog():
        state = {"rating": 0}
        star_row = ft.Row(spacing=0, alignment=ft.MainAxisAlignment.CENTER)
        rating_text = ft.Text("Tap a star to rate the fix", size=12, color=ui.MUTED, text_align=ft.TextAlign.CENTER)
        feedback = ui.text_field("Feedback (optional)", hint="How did it go?", multiline=True, max_length=1000)
        labels = ["", "Poor", "Fair", "Good", "Very good", "Excellent"]

        def draw_stars():
            star_row.controls = [
                ft.IconButton(
                    ft.Icons.STAR_ROUNDED if i <= state["rating"] else ft.Icons.STAR_OUTLINE_ROUNDED,
                    icon_color=STAR, icon_size=34, tooltip=f"{i} star{'s' if i > 1 else ''}",
                    on_click=lambda e, n=i: set_rating(n),
                )
                for i in range(1, 6)
            ]

        def set_rating(n):
            state["rating"] = n
            rating_text.value = labels[n]
            rating_text.color = ui.TEXT
            draw_stars()
            page.update()

        draw_stars()

        async def do_confirm(dialog, button):
            if not state["rating"]:
                rating_text.value = "Please choose a rating."
                rating_text.color = ui.ERROR
                return
            try:
                await issue_service.confirm(issue_id, state["rating"], (feedback.value or "").strip() or None)
            except Exception as exc:  # noqa: BLE001
                ui.snack(page, _api_message(exc), error=True)
                return
            page.pop_dialog()
            ui.snack(page, "Thanks! The issue is now closed.")
            await reload(silent=True)

        ui.confirm_dialog(
            page, "Confirm the fix",
            ft.Column([star_row, rating_text, feedback], spacing=10, tight=True, width=360),
            "Confirm & close", do_confirm,
        )

    def open_reopen_dialog():
        reason = ui.text_field("What's still wrong?", hint="e.g. The tap started leaking again this morning",
                               multiline=True, max_length=1000)

        def clear_error(e):
            if reason.error:
                reason.error = None
                page.update()

        reason.on_change = clear_error

        async def do_reopen(dialog, button):
            text = (reason.value or "").strip()
            if len(text) < 5:
                reason.error = "Please describe the problem (at least 5 characters)."
                return
            try:
                await issue_service.reopen(issue_id, text)
            except Exception as exc:  # noqa: BLE001
                ui.snack(page, _api_message(exc), error=True)
                return
            page.pop_dialog()
            ui.snack(page, "Issue reopened. The PHO office has been notified.")
            await reload(silent=True)

        ui.confirm_dialog(
            page, "Reopen this issue?",
            ft.Column([ft.Text("It goes back to the worker who fixed it.", size=13, color=ui.MUTED), reason],
                      spacing=10, tight=True, width=360),
            "Reopen", do_reopen, danger=True,
        )

    page.run_task(reload)
    return ui.screen([
        ui.back_header(page, f"Issue #{issue_id}", "Track progress and talk to the PHO office",
                       actions=[ft.IconButton(ft.Icons.REFRESH, tooltip="Refresh", icon_color=ui.PURPLE,
                                              on_click=lambda e: page.run_task(reload))]),
        body,
    ])