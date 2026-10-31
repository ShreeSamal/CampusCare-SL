"""HOME  |  side: student  |  route: /home  |  navbar tab 1

UI TODO
  [ ] Header: "Hi, <first name>"
  [ ] Summary cards row (3 cards): Open | In progress | Resolved   (counts, tap -> /issues with that filter)
  [ ] Primary Button "Report an issue" -> go(page, "/report")
  [ ] "Recent issues" section: last 3-5 issues as IssueCard (components/issue_card.py), tap -> go(page, "/issue", id=...)
  [ ] "View all" TextButton -> go(page, "/issues")
  [ ] Empty state (no issues yet) with a friendly message + report button
  [ ] Loading state (skeleton or ProgressRing) and error state with Retry
  [ ] Pull-to-refresh (or a refresh icon)
  [ ] No charts on this screen

Data TODO
  [ ] issue_service.list_my_issues() and compute counts (or a dedicated summary endpoint)
"""
import flet as ft


def view(page: ft.Page, **params) -> ft.Control:
    return ft.Container(
        padding=16,
        content=ft.Column([ft.Text("Home", size=22, weight=ft.FontWeight.BOLD), ft.Text("TODO: see docstring")]),
    )