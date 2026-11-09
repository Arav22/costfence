"""CLI entry point — costfence start, status, reset, dashboard, init."""

from __future__ import annotations

import sys

import click


@click.group()
@click.version_option()
def main() -> None:
    """costfence — real-time spending guard for AI API usage."""


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=8990, type=int, help="Bind port")
@click.option("--config", default=None, type=click.Path(), help="Config file path")
def start(host: str, port: int, config: str | None) -> None:
    """Start the costfence proxy server."""
    import os

    import uvicorn

    if config:
        os.environ["COSTFENCE_CONFIG"] = config

    click.echo(f"costfence proxy starting on {host}:{port}")
    click.echo("Point your AI tools to http://{}:{} as the API base URL".format(host, port))
    click.echo("Press Ctrl+C to stop\n")

    uvicorn.run(
        "costfence.proxy:app",
        host=host,
        port=port,
        log_level="warning",
    )


@main.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8990, type=int)
def status(host: str, port: int) -> None:
    """Show current spending status."""
    import httpx

    try:
        resp = httpx.get(f"http://{host}:{port}/costfence/status", timeout=5.0)
        data = resp.json()
    except httpx.ConnectError:
        click.echo("Error: cannot connect to costfence proxy. Is it running?", err=True)
        sys.exit(1)

    spend = data.get("spend", {})
    budgets = data.get("budgets", {})
    remaining = data.get("remaining", {})
    tokens = data.get("tokens", {})

    click.echo(f"\n  costfence — session {data.get('session_id', '?')}\n")

    for scope, key in [("Session", "per_session"), ("Hourly", "per_hour"), ("Daily", "per_day"), ("Project", "per_project")]:
        spent = spend.get(scope.lower(), 0)
        limit = budgets.get(key)
        rem = remaining.get(scope.lower())

        limit_str = f"${limit:.2f}" if limit else "unlimited"
        rem_str = f"${rem:.4f}" if rem is not None else "-"

        color = "red" if limit and spent >= limit else "green"
        click.echo(click.style(f"  {scope:10s}  ${spent:.4f} / {limit_str}  (remaining: {rem_str})", fg=color))

    click.echo(f"\n  Tokens — input: {tokens.get('input', 0):,}  output: {tokens.get('output', 0):,}\n")


@main.command()
@click.option("--scope", default="session", type=click.Choice(["session", "all"]))
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8990, type=int)
def reset(scope: str, host: str, port: int) -> None:
    """Reset spending counters."""
    import httpx

    try:
        resp = httpx.post(f"http://{host}:{port}/costfence/reset?scope={scope}", timeout=5.0)
        data = resp.json()
        click.echo(f"Reset {data.get('reset', scope)} counters.")
    except httpx.ConnectError:
        click.echo("Error: cannot connect to costfence proxy. Is it running?", err=True)
        sys.exit(1)


@main.command()
@click.option("--host", default="127.0.0.1")
@click.option("--port", default=8990, type=int)
def dashboard(host: str, port: int) -> None:
    """Open the live TUI dashboard."""
    from .dashboard import run_dashboard

    run_dashboard(host, port)


@main.command()
def init() -> None:
    """Create default config at ~/.costfence/config.yaml."""
    from .config import create_default_config

    path = create_default_config()
    click.echo(f"Created config at {path}")
    click.echo("Edit budgets, targets, and pricing in that file.")


if __name__ == "__main__":
    main()
