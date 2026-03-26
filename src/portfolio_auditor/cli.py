from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from portfolio_auditor.audit_runner import AuditRunner
from portfolio_auditor.collectors.github.client import GitHubApiError, GitHubRateLimitError
from portfolio_auditor.settings import get_settings

app = typer.Typer(help="GitHub portfolio auditor CLI.")
console = Console()


@app.command("full-run")
def full_run_command(
    owner: str = typer.Option(..., "--owner", help="GitHub username or organization."),
    refresh_clones: bool = typer.Option(
        False,
        "--refresh-clones",
        help="Re-clone repositories even if they already exist locally.",
    ),
) -> None:
    settings = get_settings()
    runner = AuditRunner(settings)

    try:
        artifacts = runner.run(
            owner=owner,
            refresh_clones=refresh_clones,
            enrich=True,
            export=True,
        )
    except GitHubRateLimitError as exc:
        snapshot_path = settings.github_raw_dir / f"{owner}_repos.json"
        console.print("[bold red]GitHub API rate limit exceeded.[/bold red]")
        console.print(str(exc))
        if snapshot_path.exists():
            console.print(
                f"[yellow]Cached snapshot available:[/yellow] {snapshot_path}"
            )
        else:
            console.print(
                "[yellow]No cached snapshot found.[/yellow] "
                "Set GITHUB_TOKEN in your environment or .env file and rerun."
            )
        raise typer.Exit(code=1) from exc
    except GitHubApiError as exc:
        console.print("[bold red]GitHub collection failed.[/bold red]")
        console.print(str(exc))
        raise typer.Exit(code=1) from exc
    finally:
        runner.close()

    console.print("")
    console.print("[bold green]Audit completed.[/bold green]")
    console.print(f"Repositories analyzed: {len(artifacts.repos)}")
    console.print(f"Scans generated: {len(artifacts.scans)}")
    console.print(f"Scores generated: {len(artifacts.scores)}")
    console.print(f"Reviews generated: {len(artifacts.reviews)}")
    console.print("")

    if artifacts.ranking is not None:
        console.print("[bold]Top repositories:[/bold]")
        for repo in artifacts.ranking.top_repos[:5]:
            console.print(
                f"  - {repo.repo_full_name}: {repo.global_score:.2f}/100 ({repo.score_label})"
            )

    processed_dir = settings.processed_dir / owner
    console.print(f"Processed artifacts directory: {Path(processed_dir)}")


if __name__ == "__main__":
    app()