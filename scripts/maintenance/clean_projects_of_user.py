#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "httpx",
#     "pydantic[email]",
#     "rich",
#     "tenacity",
#     "typer",
# ]
# ///

import asyncio
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
    TaskID,
    TextColumn,
    TimeRemainingColumn,
)
from rich.table import Table
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

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
    """Display a formatted status message with an icon and color based on status type.

    Prints a message to the console with appropriate visual formatting including
    status-specific icons and colors for better user experience.
    """
    status_map = {
        "info": ("ℹ️", "blue"),  # noqa: RUF001
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
    r = await client.get(path, params={"type": "all", "show_hidden": True})
    r.raise_for_status()
    assert r.status_code == codes.OK  # nosec
    response_dict = r.json()
    project_data = response_dict["data"]
    return ProjectInfo(
        uuid=project_data.get("uuid", project_id),
        name=project_data.get("name"),
    )


async def get_user_project_count(client: AsyncClient) -> int:
    """Fetch the total number of projects for the user."""
    r = await client.get(
        "/projects", params={"type": "all", "limit": 1, "show_hidden": True}
    )
    r.raise_for_status()
    response_dict = r.json()
    return response_dict.get("_meta", {}).get("total", 0)


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
        table.add_row(project.uuid, name)

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
                project.uuid,
                project.error_message or "Unknown error",
            )

        console.print(error_table)


async def _process_batch(
    client: AsyncClient,
    *,
    batch: list[ProjectInfo],
    progress: Progress,
    task_id: TaskID,
    dry_run: bool,
) -> tuple[int, list[ProjectInfo]]:
    """Process a single batch of projects."""
    if not batch:
        return 0, []

    if dry_run:
        for project in batch:
            progress.console.print(
                f"[dim]Would delete project: {project.uuid} ({project.name})[/dim]"
            )
            progress.update(task_id, advance=1)
        return 0, []

    progress.update(
        task_id, description=f"[cyan]Deleting batch of {len(batch)} projects...[/cyan]"
    )

    tasks = [delete_project(client, project) for project in batch]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    deleted_count = 0
    failed_projects = []

    for i, result in enumerate(results):
        progress.update(task_id, advance=1)
        project = batch[i]

        if isinstance(result, Exception):
            project.status = "failed"
            project.error_message = f"Exception: {result}"
            failed_projects.append(project)
            progress.console.print(
                f"[red]Failed to delete {project.uuid}: {project.error_message}[/red]"
            )
            continue

        # result is ProjectInfo
        proj = result
        if proj.status == "failed":
            failed_projects.append(proj)
            progress.console.print(
                f"[red]Failed to delete {proj.uuid}: {proj.error_message}[/red]"
            )
        elif proj.status == "deleted":
            deleted_count += 1

    progress.console.print(f"[green]Deleted batch of {len(batch)} projects[/green]")
    return deleted_count, failed_projects


@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(1),
    retry=retry_if_exception_type((HTTPStatusError, Exception)),
    reraise=True,
)
async def _fetch_batch(client: AsyncClient, batch_size: int, offset: int) -> list[dict]:
    """Fetch a batch of projects with retries."""
    r = await client.get(
        "/projects",
        params={
            "type": "all",
            "limit": batch_size,
            "offset": offset,
            "show_hidden": True,
        },
    )
    r.raise_for_status()
    return r.json().get("data", [])


async def process_deletion_stream(
    client: AsyncClient,
    *,
    progress: Progress,
    task_id: TaskID,
    batch_size: int,
    dry_run: bool,
) -> tuple[int, list[ProjectInfo]]:
    """Process projects for deletion in batches using streaming approach.

    Continuously fetches and processes projects in batches until no more projects
    are available or an error occurs. Handles pagination automatically and provides
    progress tracking for the deletion operation.

    Returns:
        A tuple containing the total number of successfully deleted projects and
        a list of projects that failed to be deleted.
    """
    deleted_count = 0
    all_failed_projects: list[ProjectInfo] = []
    offset = 0

    while True:
        try:
            projects_data = await _fetch_batch(client, batch_size, offset)
        except HTTPStatusError as exc:
            if exc.response.status_code == codes.NOT_FOUND:
                # After retries, if we still get 404, assume end of stream
                break
            progress.console.print(
                f"[red]Error fetching projects after retries: {exc}[/red]"
            )
            break
        except Exception as exc:  # pylint: disable=broad-except
            progress.console.print(
                f"[red]Error fetching projects after retries: {exc}[/red]"
            )
            break

        if not projects_data:
            break

        batch = [
            ProjectInfo(
                uuid=p.get("uuid"),
                name=p.get("name"),
            )
            for p in projects_data
        ]

        count, failed = await _process_batch(
            client, batch=batch, progress=progress, task_id=task_id, dry_run=dry_run
        )

        deleted_count += count
        all_failed_projects.extend(failed)

        if dry_run:
            offset += len(batch)
        else:
            offset += len(failed)

    return deleted_count, all_failed_projects


async def clean_single_project(
    client: AsyncClient, *, project_id: str, dry_run: bool
) -> int:
    """Handle deletion of a single project."""
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

    console.print("\n[bold yellow]Delete this project?[/bold yellow]")
    if not typer.confirm(""):
        _display_status_message("Deletion cancelled", "info")
        return 0

    result = await delete_project(client, project)

    if result.status == "deleted":
        _display_status_message("Project successfully deleted", "success")
        return 0

    _display_status_message(
        f"Failed to delete project: {result.error_message}", "error"
    )
    return 1


async def clean_all_projects(
    client: AsyncClient,
    *,
    batch_size: int,
    dry_run: bool,
    username: str,
) -> int:
    """Handle deletion of all projects for a user."""
    console.print()

    with console.status("[cyan]Checking project count...[/cyan]"):
        total_projects = await get_user_project_count(client)

    if total_projects == 0:
        _display_status_message("No projects found to delete", "warning")
        return 0

    _display_status_message(f"Found {total_projects} projects", "info")

    if not dry_run:
        console.print(
            f"\n[bold yellow]Are you sure you want to delete ALL {total_projects} projects for {username}?[/bold yellow]"
        )
        if not typer.confirm(""):
            _display_status_message("Deletion cancelled", "info")
            return 0
    else:
        _display_status_message(
            f"Starting DRY-RUN ({total_projects} projects would be deleted)", "warning"
        )

    _display_status_message("Fetching and processing projects...", "info")

    stats = DeletionStats(start_time=datetime.now(tz=UTC))
    stats.total_projects = total_projects

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.1f}%"),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        task_id = progress.add_task(
            "[cyan]Processing projects...[/cyan]", total=total_projects
        )

        stats.deleted_count, failed_projects = await process_deletion_stream(
            client,
            progress=progress,
            task_id=task_id,
            batch_size=batch_size,
            dry_run=dry_run,
        )
        stats.failed_count = len(failed_projects)

    if stats.total_projects == 0:
        _display_status_message("No projects found", "warning")
        return 1

    console.print()
    _display_status_message(f"Found {stats.total_projects} projects total", "info")

    if dry_run:
        _display_status_message(
            f"DRY-RUN: {stats.total_projects} projects would have been deleted",
            "warning",
        )
        return 0

    stats.end_time = datetime.now(tz=UTC)
    console.print()
    _display_summary_report(stats, failed_projects)

    return 0


async def clean(
    endpoint: URL,
    username: EmailStr,
    password: SecretStr,
    project_id: str | None,
    *,
    batch_size: int,
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
    try:
        async with AsyncClient(
            base_url=endpoint.join("v0"), timeout=DEFAULT_TIMEOUT, follow_redirects=True
        ) as client:
            await login_user(client, username, password)

            if project_id:
                return await clean_single_project(
                    client, project_id=project_id, dry_run=dry_run
                )

            return await clean_all_projects(
                client,
                batch_size=batch_size,
                dry_run=dry_run,
                username=username,
            )

    except HTTPStatusError as exc:
        error_panel = Panel(
            f"HTTP Error {exc.response.status_code}\n{exc.response.text}",
            title="[bold red]API Error[/bold red]",
            style="red",
        )
        console.print(error_panel)
        return 1

    except Exception as exc:  # pylint: disable=broad-except
        error_panel = Panel(
            f"{type(exc).__name__}: {exc}",
            title="[bold red]Unexpected Error[/bold red]",
            style="red",
        )
        console.print(error_panel)
        return 1


def main(
    endpoint: Annotated[str, typer.Argument(help="oSparc type endpoint URL")],
    username: Annotated[str, typer.Argument(help="User's email address")],
    password: Annotated[str, typer.Argument(help="User's password")],
    project_id: Annotated[
        str | None,
        typer.Option(help="optional project UUID if only one project shall be deleted"),
    ] = None,
    *,
    batch_size: Annotated[
        int,
        typer.Option(
            "--batch-size",
            "-b",
            help="Number of projects to delete concurrently",
        ),
    ] = DEFAULT_BATCH_SIZE,
    dry_run: Annotated[
        bool,
        typer.Option(
            "--dry-run", help="Show what would be deleted without actually deleting"
        ),
    ] = False,
) -> int:
    """Clean all projects for a given user and endpoint."""
    console.print(Panel("[bold cyan]osparc-simcore Project Cleaner[/bold cyan]"))

    return asyncio.run(
        clean(
            URL(endpoint),
            TypeAdapter(EmailStr).validate_python(username),
            SecretStr(password),
            project_id,
            batch_size=batch_size,
            dry_run=dry_run,
        )
    )


if __name__ == "__main__":
    typer.run(main)
