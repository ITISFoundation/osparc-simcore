#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
#     "pydantic[email]",
#     "rich",
#     "typer",
# ]
# ///

import asyncio
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated

import typer
from httpx import URL, AsyncClient, HTTPStatusError, Timeout, codes
from pydantic import EmailStr, SecretStr, TypeAdapter
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table

DEFAULT_TIMEOUT = Timeout(30.0)
DEFAULT_BATCH_SIZE = 10
DEFAULT_PAGE_SIZE = 50

console = Console()


@dataclass
class DeletionStats:
    """Track deletion operation statistics."""

    total_projects: int = 0
    deleted_count: int = 0
    failed_count: int = 0
    start_time: datetime | None = None
    end_time: datetime | None = None

    @property
    def duration_seconds(self) -> float:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

    @property
    def success_rate(self) -> float:
        if self.total_projects == 0:
            return 0.0
        return (self.deleted_count / self.total_projects) * 100


@dataclass
class ProjectInfo:
    """Project information container."""

    uuid: str
    name: str | None = None
    status: str = "pending"
    error_message: str | None = None


def _display_status_message(message: str, status: str = "info") -> None:
    """Display a formatted status message."""
    status_map = {
        "info": ("ℹ️", "blue"),
        "success": ("✓", "green"),
        "warning": ("⚠", "yellow"),
        "error": ("✗", "red"),
    }
    icon, color = status_map.get(status, ("•", "white"))
    console.print(f"[{color}]{icon} {message}[/{color}]")


async def login_user(client: AsyncClient, email: EmailStr, password: SecretStr) -> None:
    """Authenticate user with email and password."""
    with console.status("[cyan]Authenticating...[/cyan]"):
        path = "/auth/login"
        r = await client.post(
            path, json={"email": email, "password": password.get_secret_value()}
        )
        r.raise_for_status()
    _display_status_message(f"Successfully logged in as {email}", "success")


async def get_project_for_user(
    client: AsyncClient, project_id: str
) -> ProjectInfo | None:
    """Fetch a single project by ID."""
    path = f"/projects/{project_id}"
    r = await client.get(path, params={"type": "user"})
    r.raise_for_status()
    assert r.status_code == codes.OK  # nosec
    response_dict = r.json()
    project_data = response_dict["data"]
    return ProjectInfo(
        uuid=project_data.get("uuid", project_id),
        name=project_data.get("name"),
    )


async def projects_iterator(
    client: AsyncClient,
    page_size: int = DEFAULT_PAGE_SIZE,
    on_total_count: Callable[[int], None] | None = None,
) -> AsyncGenerator[ProjectInfo]:
    """
    Async generator that yields projects page by page.

    Handles pagination automatically and yields projects one at a time
    without loading all into memory at once.
    """
    next_link: str | None = "/projects"
    is_first_page = True

    while next_link:
        r = await client.get(next_link, params={"type": "user", "limit": page_size})
        r.raise_for_status()

        if r.status_code != codes.OK:
            break

        response_dict = r.json()
        projects_data = response_dict.get("data", [])

        if is_first_page and on_total_count:
            total = response_dict.get("_meta", {}).get("total")
            if total is not None:
                on_total_count(total)
            is_first_page = False

        for project_data in projects_data:
            yield ProjectInfo(
                uuid=project_data.get("uuid"),
                name=project_data.get("name"),
            )

        # Get next page link if available
        next_link = response_dict.get("_links", {}).get("next")


async def delete_project(client: AsyncClient, project: ProjectInfo) -> ProjectInfo:
    """Delete a single project and update its status."""
    path = f"/projects/{project.uuid}"
    try:
        r = await client.delete(path)
        if r.status_code == codes.NO_CONTENT:
            project.status = "deleted"
        else:
            project.status = "failed"
            project.error_message = f"Status {r.status_code}: {r.reason_phrase}"
    except Exception as exc:  # pylint: disable=broad-except
        project.status = "failed"
        project.error_message = str(exc)

    return project


def _display_projects_table(projects: list[ProjectInfo]) -> None:
    """Display a formatted table of projects."""
    table = Table(
        title="Projects to be Deleted", show_header=True, header_style="bold cyan"
    )
    table.add_column("UUID", style="magenta")
    table.add_column("Name", style="green")

    for project in projects:
        name = project.name or "[dim]Unknown[/dim]"
        table.add_row(project.uuid[:8] + "...", name)

    console.print(table)


def _display_summary_report(
    stats: DeletionStats, failed_projects: list[ProjectInfo]
) -> None:
    """Display a comprehensive summary report."""
    summary_text = f"""
[bold cyan]╔═══════════════════════════════════════════╗[/bold cyan]
[bold cyan]║[/bold cyan]  [bold]DELETION SUMMARY REPORT[/bold]  [bold cyan]║[/bold cyan]
[bold cyan]╚═══════════════════════════════════════════╝[/bold cyan]

[bold]Total Projects:[/bold]      {stats.total_projects}
[bold green]Successfully Deleted:[/bold green]  {stats.deleted_count}
[bold red]Failed:[/bold red]               {stats.failed_count}
[bold cyan]Success Rate:[/bold cyan]       {stats.success_rate:.1f}%
[bold yellow]Duration:[/bold yellow]         {stats.duration_seconds:.2f}s
"""

    console.print(summary_text)

    if failed_projects:
        error_table = Table(
            title="Failed Deletions", show_header=True, header_style="bold red"
        )
        error_table.add_column("UUID", style="magenta")
        error_table.add_column("Error", style="red")

        for project in failed_projects:
            error_table.add_row(
                project.uuid[:8] + "...",
                project.error_message or "Unknown error",
            )

        console.print(error_table)


async def process_deletion_batches(
    client: AsyncClient,
    page_size: int,
    batch_size: int = DEFAULT_BATCH_SIZE,
    stats: DeletionStats | None = None,
    dry_run: bool = False,
) -> tuple[int, int, list[ProjectInfo]]:
    """
    Process project deletions in batches.

    Yields batches of projects to delete without loading all into memory.
    Returns count of deleted, failed, and list of failed projects.
    """
    if stats is None:
        stats = DeletionStats()

    deleted_count = 0
    failed_projects: list[ProjectInfo] = []

    batch: list[ProjectInfo] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Processing projects...[/cyan]", total=None)

        def set_total(total: int) -> None:
            progress.update(task, total=total)
            if stats:
                stats.total_projects = total

        projects_iter = projects_iterator(
            client, page_size=page_size, on_total_count=set_total
        )

        async for project in projects_iter:
            progress.update(task, advance=1)

            if dry_run:
                progress.console.print(
                    f"[dim]Would delete project: {project.uuid} ({project.name})[/dim]"
                )
                continue

            batch.append(project)
            if len(batch) >= batch_size:
                # Process this batch
                progress.update(
                    task,
                    description=f"[cyan]Deleting batch of {len(batch)} projects...[/cyan]",
                )
                deleted_in_batch = await _delete_batch(client, batch, progress)
                deleted_count += deleted_in_batch
                progress.console.print(
                    f"[green]Deleted batch of {len(batch)} projects[/green]"
                )

                for proj in batch:
                    if proj.status == "failed":
                        failed_projects.append(proj)
                        progress.console.print(
                            f"[red]Failed to delete {proj.uuid}: {proj.error_message}[/red]"
                        )
                    elif proj.status == "deleted":
                        deleted_count += 1

                batch = []

        # Process remaining projects
        if batch and not dry_run:
            progress.update(
                task,
                description=f"[cyan]Deleting final batch of {len(batch)} projects...[/cyan]",
            )
            deleted_in_batch = await _delete_batch(client, batch, progress)
            deleted_count += deleted_in_batch
            progress.console.print(
                f"[green]Deleted final batch of {len(batch)} projects[/green]"
            )

            for proj in batch:
                if proj.status == "failed":
                    failed_projects.append(proj)
                    progress.console.print(
                        f"[red]Failed to delete {proj.uuid}: {proj.error_message}[/red]"
                    )
                elif proj.status == "deleted":
                    deleted_count += 1

    stats.deleted_count = deleted_count
    stats.failed_count = len(failed_projects)
    return deleted_count, len(failed_projects), failed_projects


async def _delete_batch(
    client: AsyncClient, batch: list[ProjectInfo], progress: Progress
) -> int:
    """Delete a batch of projects concurrently."""
    tasks = [delete_project(client, project) for project in batch]
    results = await asyncio.gather(*tasks, return_exceptions=False)

    return sum(1 for proj in results if proj.status == "deleted")


async def clean(
    endpoint: URL,
    username: EmailStr,
    password: SecretStr,
    project_id: str | None,
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    page_size: int = DEFAULT_PAGE_SIZE,
    dry_run: bool = False,
) -> int:
    """
    Main cleanup function.

    Args:
        endpoint: API endpoint URL
        username: User email
        password: User password
        project_id: Optional specific project to delete
        batch_size: Number of projects to delete concurrently
        page_size: Number of projects per API page
        dry_run: If True, only show what would be deleted without deleting

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    stats = DeletionStats(start_time=datetime.now(tz=UTC))

    try:
        async with AsyncClient(
            base_url=endpoint.join("v0"), timeout=DEFAULT_TIMEOUT, follow_redirects=True
        ) as client:
            await login_user(client, username, password)

            # Handle single project deletion
            if project_id:
                with console.status("[cyan]Fetching project...[/cyan]"):
                    project = await get_project_for_user(client, project_id)

                if not project:
                    _display_status_message(f"Project {project_id} not found!", "error")
                    return 1

                console.print()
                _display_projects_table([project])

                if dry_run:
                    _display_status_message(
                        "DRY-RUN: Project would be deleted (not actually deleted)",
                        "warning",
                    )
                    return 0

                if not typer.confirm(
                    "\n[bold yellow]Delete this project?[/bold yellow]"
                ):
                    _display_status_message("Deletion cancelled", "info")
                    return 0

                result = await delete_project(client, project)
                stats.total_projects = 1
                stats.end_time = datetime.now(tz=UTC)

                if result.status == "deleted":
                    stats.deleted_count = 1
                    _display_status_message("Project successfully deleted", "success")
                else:
                    stats.failed_count = 1
                    _display_status_message(
                        f"Failed to delete project: {result.error_message}", "error"
                    )
                    return 1

                return 0

            # Handle multiple projects deletion
            console.print()

            if not dry_run:
                if not typer.confirm(
                    f"\n[bold yellow]Are you sure you want to delete ALL projects for {username}?[/bold yellow]"
                ):
                    _display_status_message("Deletion cancelled", "info")
                    return 0
            else:
                _display_status_message(
                    "Starting DRY-RUN (no projects will be deleted)", "warning"
                )

            _display_status_message("Fetching and processing projects...", "info")

            (
                deleted_count,
                failed_count,
                failed_projects,
            ) = await process_deletion_batches(
                client,
                page_size=page_size,
                batch_size=batch_size,
                stats=stats,
                dry_run=dry_run,
            )

            if stats.total_projects == 0:
                _display_status_message("No projects found", "warning")
                return 1

            console.print()
            _display_status_message(
                f"Found {stats.total_projects} projects total", "info"
            )

            if dry_run:
                _display_status_message(
                    f"DRY-RUN: {stats.total_projects} projects would have been deleted",
                    "warning",
                )
                return 0

            stats.end_time = datetime.now(tz=UTC)
            console.print()
            _display_summary_report(stats, failed_projects)

            if failed_count > 0:
                return 1

            return 0

    except HTTPStatusError as exc:
        stats.end_time = datetime.now(tz=UTC)
        error_panel = Panel(
            f"HTTP Error {exc.response.status_code}\n{exc.response.text}",
            title="[bold red]API Error[/bold red]",
            style="red",
        )
        console.print(error_panel)
        return 1

    except Exception as exc:  # pylint: disable=broad-except
        stats.end_time = datetime.now(tz=UTC)
        error_panel = Panel(
            f"{type(exc).__name__}: {exc}",
            title="[bold red]Unexpected Error[/bold red]",
            style="red",
        )
        console.print(error_panel)
        return 1


def main(
    endpoint: str,
    username: str,
    password: str,
    project_id: str | None = None,
    *,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            "-b",
            help="Number of projects to delete concurrently",
        ),
    ] = DEFAULT_BATCH_SIZE,
    page_size: Annotated[
        int,
        typer.Option(
            "--page-size",
            "-p",
            help="Number of projects per API page",
        ),
    ] = DEFAULT_PAGE_SIZE,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be deleted without actually deleting"
        ),
    ] = False,
) -> int:
    """Clean all projects for a given user."""
    console.print(Panel("[bold cyan]osparc-simcore Project Cleaner[/bold cyan]"))

    return asyncio.get_event_loop().run_until_complete(
        clean(
            URL(endpoint),
            TypeAdapter(EmailStr).validate_python(username),
            SecretStr(password),
            project_id,
            batch_size=batch_size,
            page_size=page_size,
            dry_run=dry_run,
        )
    )


if __name__ == "__main__":
    typer.run(main)
