"""Rich TUI dashboard for live cost monitoring."""

from __future__ import annotations

import time

from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from .db import UsageDB


def _cost_color(amount: float, limit: float | None) -> str:
    if limit is None:
        return "green"
    ratio = amount / limit if limit > 0 else 0
    if ratio >= 0.9:
        return "red bold"
    if ratio >= 0.7:
        return "yellow"
    return "green"


def _format_cost(amount: float) -> str:
    if amount < 0.01:
        return f"${amount:.6f}"
    return f"${amount:.4f}"


def _build_budget_table(status: dict) -> Table:
    table = Table(title="Budget Status", expand=True)
    table.add_column("Scope", style="cyan")
    table.add_column("Spent", justify="right")
    table.add_column("Limit", justify="right")
    table.add_column("Remaining", justify="right")

    spend = status.get("spend", {})
    remaining = status.get("remaining", {})
    budgets = status.get("budgets", {})

    for scope, budget_key in [("Session", "per_session"), ("Hourly", "per_hour"), ("Daily", "per_day"), ("Project", "per_project")]:
        spent = spend.get(scope.lower(), 0)
        limit = budgets.get(budget_key)
        rem = remaining.get(scope.lower())

        limit_str = f"${limit:.2f}" if limit else "unlimited"
        rem_str = _format_cost(rem) if rem is not None else "-"
        color = _cost_color(spent, limit)

        table.add_row(scope, Text(_format_cost(spent), style=color), limit_str, rem_str)

    return table


def _build_recent_table(db: UsageDB) -> Table:
    table = Table(title="Recent Requests", expand=True)
    table.add_column("Time", style="dim")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("In", justify="right")
    table.add_column("Out", justify="right")
    table.add_column("Cost", justify="right", style="green")

    for row in db.get_recent(10):
        elapsed = time.time() - row["timestamp"]
        if elapsed < 60:
            time_str = f"{elapsed:.0f}s ago"
        elif elapsed < 3600:
            time_str = f"{elapsed / 60:.0f}m ago"
        else:
            time_str = f"{elapsed / 3600:.1f}h ago"

        table.add_row(
            time_str,
            row["provider"],
            row["model"][:30],
            f'{row["input_tokens"]:,}',
            f'{row["output_tokens"]:,}',
            _format_cost(row["cost"]),
        )

    return table


def _build_provider_table(db: UsageDB) -> Table:
    table = Table(title="Cost by Provider", expand=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Total Cost", justify="right", style="green")

    for provider, cost in db.get_cost_by_provider().items():
        table.add_row(provider, _format_cost(cost))

    tokens = db.get_token_totals()
    table.add_section()
    table.add_row("Total Input Tokens", f'{tokens["input"]:,}')
    table.add_row("Total Output Tokens", f'{tokens["output"]:,}')

    return table


def render_dashboard(status: dict, db: UsageDB) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="left"),
        Layout(name="right"),
    )
    layout["left"].split_column(
        Layout(name="budgets"),
        Layout(name="providers"),
    )

    session_id = status.get("session_id", "unknown")
    layout["header"].update(
        Panel(Text(f"costfence — session {session_id}", style="bold white", justify="center"), style="blue")
    )
    layout["budgets"].update(Panel(_build_budget_table(status)))
    layout["providers"].update(Panel(_build_provider_table(db)))
    layout["right"].update(Panel(_build_recent_table(db)))

    return layout


def run_dashboard(host: str = "127.0.0.1", port: int = 8990) -> None:
    import httpx

    console = Console()
    db = UsageDB()
    client = httpx.Client(timeout=5.0)
    url = f"http://{host}:{port}/costfence/status"

    console.print(f"[bold]costfence dashboard[/bold] — connecting to {url}")

    with Live(console=console, refresh_per_second=2) as live:
        while True:
            try:
                resp = client.get(url)
                status = resp.json()
                live.update(render_dashboard(status, db))
            except (httpx.ConnectError, httpx.ReadTimeout):
                live.update(Panel("[red]Cannot connect to costfence proxy. Is it running?[/red]"))
            except KeyboardInterrupt:
                break
            time.sleep(0.5)
