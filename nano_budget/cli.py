from __future__ import annotations
import datetime
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich import box

app = typer.Typer(name="nano-budget", add_completion=False)
console = Console(force_terminal=True)


def _budget(path: str = "~/.nano-budget"):
    from nano_budget.budget import Budget
    return Budget(path=path)


@app.command()
def stats(
    today: bool = typer.Option(False, "--today", "-t"),
    path: str = typer.Option("~/.nano-budget", "--path"),
):
    """Show total spending across all nano-eco components."""
    b = _budget(path)
    data = b.today() if today else b.total()
    label = "today" if today else "all time"

    console.print(f"\n[bold]nano-budget[/bold] ({label})")
    console.print(f"  Total cost:    [bold green]${data['cost_usd']:.6f}[/bold green]")
    console.print(f"  Total tokens:  [bold]{data['total_tokens']:,}[/bold]  "
                  f"([dim]in: {data['input_tokens']:,}  out: {data['output_tokens']:,}[/dim])")
    console.print(f"  Total calls:   {data['calls']:,}")


@app.command()
def breakdown(
    by: str = typer.Option("source", "--by", "-b", help="source | agent | model"),
    today: bool = typer.Option(False, "--today", "-t"),
    path: str = typer.Option("~/.nano-budget", "--path"),
):
    """Show cost breakdown by source/agent/model."""
    b = _budget(path)
    label = "today" if today else "all time"

    if by == "source":
        rows = b.by_source(today_only=today)
        col = "Source (component)"
        key = "source"
    elif by == "agent":
        rows = b.by_agent(today_only=today)
        col = "Agent"
        key = "agent_id"
    elif by == "model":
        rows = b.by_model(today_only=today)
        col = "Model"
        key = "model"
    else:
        console.print("[red]--by must be source, agent, or model[/red]")
        raise typer.Exit(1)

    if not rows:
        console.print(f"[dim]No data ({label})[/dim]")
        return

    t = Table(box=box.SIMPLE, show_header=True, header_style="bold")
    t.add_column(col)
    t.add_column("Calls", justify="right")
    t.add_column("Input Tok", justify="right")
    t.add_column("Output Tok", justify="right")
    t.add_column("Cost USD", justify="right")

    for r in rows:
        t.add_row(
            r[key], str(r["calls"]),
            f"{r['input_tokens']:,}", f"{r['output_tokens']:,}",
            f"[green]${r['cost_usd']:.6f}[/green]",
        )

    console.print(f"\n[bold]Cost breakdown by {by}[/bold] ({label})")
    console.print(t)


@app.command()
def estimate(
    model: str = typer.Argument(..., help="Model name"),
    input_tokens: int = typer.Option(1000, "--in", help="Input tokens"),
    output_tokens: int = typer.Option(500, "--out", help="Output tokens"),
):
    """Estimate cost for a model call."""
    from nano_budget.budget import Budget
    cost = Budget.estimate(model, input_tokens, output_tokens)
    console.print(f"\nEstimate: [bold green]${cost:.6f}[/bold green]")
    console.print(f"  Model:  {model}")
    console.print(f"  Input:  {input_tokens:,} tokens")
    console.print(f"  Output: {output_tokens:,} tokens\n")


@app.command()
def limit(
    scope: str = typer.Argument("global", help="global | agent:id | session:id"),
    usd: Optional[float] = typer.Option(None, "--usd", help="USD limit"),
    tokens: Optional[int] = typer.Option(None, "--tokens", help="Token limit"),
    alert: float = typer.Option(0.8, "--alert", help="Alert threshold (0-1)"),
    path: str = typer.Option("~/.nano-budget", "--path"),
):
    """Set a spending limit for a scope."""
    b = _budget(path)
    b.set_limit(scope=scope, limit_usd=usd, limit_tokens=tokens, alert_at=alert)
    console.print(f"[green]Budget set[/green] for [bold]{scope}[/bold]")
    if usd:
        console.print(f"  Limit: ${usd:.4f} USD")
    if tokens:
        console.print(f"  Limit: {tokens:,} tokens")


@app.command()
def remaining(
    scope: str = typer.Argument("global"),
    path: str = typer.Option("~/.nano-budget", "--path"),
):
    """Show remaining budget for a scope."""
    b = _budget(path)
    r = b.remaining(scope)
    console.print(f"\n[bold]Budget: {scope}[/bold]")
    if r.get("no_limit"):
        console.print("  [dim]No limit set[/dim]")
    else:
        console.print(f"  Used:      [yellow]${r.get('used_usd', 0):.6f}[/yellow]")
        if "limit_usd" in r:
            console.print(f"  Limit:     ${r['limit_usd']:.4f}")
            console.print(f"  Remaining: [green]${r['remaining_usd']:.6f}[/green]  ({r.get('pct_used', 0):.1f}% used)")
