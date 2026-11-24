from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from plasma_inspector.adapters.fairmast import FairMastAdapter
from plasma_inspector.audit import audit_shot

app = typer.Typer(help="Inspect and audit FAIR-MAST data.", no_args_is_help=True)
catalog = typer.Typer(help="Search the FAIR-MAST metadata catalog.")
shot = typer.Typer(help="Inspect a shot and its signals.")
audit = typer.Typer(help="Run deterministic validation rules.")
rules = typer.Typer(help="List implemented validation rules.")
app.add_typer(catalog, name="catalog"); app.add_typer(shot, name="shot"); app.add_typer(audit, name="audit"); app.add_typer(rules, name="rules")
console = Console()


PREFERRED_COLUMNS: list[tuple[str, str]] = [
    ("shot_id", "Shot ID"),
    ("campaign", "Campaign"),
    ("timestamp", "Timestamp"),
    ("plasma_max_current", "Max Ip (kA)"),
    ("divertor_config", "Divertor"),
    ("shot_summary", "Summary"),
]


@catalog.command("search")
def search(
    level: int = typer.Option(2, min=1, max=2),
    limit: int = typer.Option(20, min=1, max=200),
    q: str | None = None,
    json_output: bool = typer.Option(False, "--json"),
    all_columns: bool = typer.Option(False, "--all-columns", help="Display all metadata columns"),
) -> None:
    rows = FairMastAdapter(level).list_shots(limit=limit, query=q)
    if json_output:
        typer.echo(json.dumps(rows, default=str))
        return
    if not rows:
        console.print(f"[yellow]No shots found in FAIR-MAST Level {level} catalog matching criteria.[/yellow]")
        return

    table = Table(title=f"FAIR-MAST Level {level} Catalog ({len(rows)} shots)")
    if all_columns:
        cols = [(k, k) for k in rows[0]]
    else:
        cols = [(k, label) for k, label in PREFERRED_COLUMNS if k in rows[0]]
        if not cols:
            cols = [(k, k) for k in list(rows[0].keys())[:6]]

    for _, label in cols:
        table.add_column(label)

    for row in rows:
        row_vals: list[str] = []
        for col_name, _ in cols:
            val = row.get(col_name)
            if val is None or val == "":
                row_vals.append("—")
            elif isinstance(val, float):
                row_vals.append(f"{val:.2f}")
            else:
                row_vals.append(str(val)[:60])
        table.add_row(*row_vals)
    console.print(table)


@shot.command("inspect")
def inspect(shot_id: int, level: int = typer.Option(2, min=1, max=2)) -> None:
    adapter = FairMastAdapter(level)
    console.print_json(json.dumps({"metadata": adapter.get_shot_metadata(shot_id), "signals": adapter.list_signals(shot_id)}, default=str))


@audit.command("run")
def run_audit(shot_id: int, level: int = typer.Option(2, min=1, max=2), group: str = typer.Option("summary"), output: Path | None = None) -> None:
    report = audit_shot(shot_id, level, group)
    rendered = report.model_dump_json(indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True); output.write_text(rendered + "\n")
        console.print(f"Audit report written to {output}")
    else: typer.echo(rendered)


@rules.command("list")
def list_rules() -> None:
    from plasma_inspector.api import rules as list_api_rules
    console.print_json(json.dumps(list_api_rules()))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run local API; binds loopback by default."""
    uvicorn.run("plasma_inspector.api:app", host=host, port=port)
