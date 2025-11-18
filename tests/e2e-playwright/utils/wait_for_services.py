#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "aiodocker",
#     "aiofiles",
#     "arrow",
#     "pyyaml",
#     "rich",
#     "tenacity",
#     "typer",
# ]
# ///

import asyncio
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import aiodocker
import arrow
import typer
import yaml
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from tenacity import retry, retry_if_result, stop_after_delay, wait_fixed
from tenacity.before_sleep import before_sleep_log

# Configure logging to be less verbose for prettier output
logging.basicConfig(level=logging.ERROR)
_logger = logging.getLogger(__name__)

_console = Console()

_current_dir = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)

_WAIT_BEFORE_RETRY = 10
_MAX_WAIT_TIME = 5 * 60

# SEE https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/

_PRE_STATES = [
    "new",  # The task was initialized.
    "pending",  # Resources for the task were allocated.
    "assigned",  # Docker assigned the task to nodes.
    "accepted",  # The task was accepted by a worker node. If a worker node rejects the task, the state changes to REJECTED.
    "preparing",  # Docker is preparing the task.
    "starting",  # Docker is starting the task.
]

_RUNNING_STATE = "running"  # The task is executing.

_FAILED_STATES = [
    "complete",  # The task exited without an error code.
    "failed",  # The task exited with an error code.
    "shutdown",  # Docker requested the task to shut down.
    "rejected",  # The worker node rejected the task.
    "orphaned",  # The node was down for too long.
    "remove",  # The task is not terminal but the associated service was removed or scaled down.
]


def _get_status_emoji_and_color(state: str) -> tuple[str, str]:
    """Get emoji and color for service state."""
    if state == _RUNNING_STATE:
        return "✅", "green"
    if state in _PRE_STATES:
        return "🔄", "yellow"
    if state in _FAILED_STATES:
        return "❌", "red"
    return "❓", "white"


def _create_services_table(service_statuses: dict[str, dict[str, Any]]) -> Table:
    """Create a rich table showing service statuses."""
    table = Table(
        title="🐳 Docker Swarm Services Status",
        show_header=True,
        header_style="bold magenta",
    )

    table.add_column("Service", style="cyan", width=25)
    table.add_column("Status", justify="center", width=10)
    table.add_column("Replicas", justify="center", width=10)
    table.add_column("Start Time", justify="right", width=12)
    table.add_column("Tasks Summary", width=60)

    for service_name, status in service_statuses.items():
        emoji, color = _get_status_emoji_and_color(status["state"])

        replicas_text = f"{status['running_replicas']}/{status['expected_replicas']}"
        if status["running_replicas"] == status["expected_replicas"]:
            replicas_style = "green"
        elif status["running_replicas"] > 0:
            replicas_style = "yellow"
        else:
            replicas_style = "red"

        start_time_text = (
            f"{status['start_time']:.1f}s" if status["start_time"] is not None else "⏳"
        )

        # Create a compact task summary
        tasks_summary = ""
        if status.get("task_states"):
            state_counts = {}
            for state in status["task_states"]:
                state_counts[state] = state_counts.get(state, 0) + 1

            summary_parts = []
            for state, count in state_counts.items():
                emoji, _ = _get_status_emoji_and_color(state)
                summary_parts.append(f"{emoji} {state}: {count}")
            tasks_summary = " | ".join(summary_parts)

        table.add_row(
            service_name,
            f"[{color}]{emoji}[/{color}]",
            f"[{replicas_style}]{replicas_text}[/{replicas_style}]",
            (
                f"[green]{start_time_text}[/green]"
                if status["start_time"] is not None
                else f"[yellow]{start_time_text}[/yellow]"
            ),
            tasks_summary,
        )

    return table


def _osparc_simcore_root_dir() -> Path:
    WILDCARD = "services/web/server"

    root_dir = Path(_current_dir)
    while not any(root_dir.glob(WILDCARD)) and root_dir != Path("/"):
        root_dir = root_dir.parent

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


def _core_docker_compose_file() -> Path:
    stack_files = list(_osparc_simcore_root_dir().glob(".stack-simcore*"))
    assert stack_files
    return stack_files[0]


def _core_services() -> list[str]:
    with _core_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return list(dc_specs["services"].keys())


def _ops_docker_compose_file() -> Path:
    return _osparc_simcore_root_dir() / ".stack-ops.yml"


def _ops_services() -> list[str]:
    with _ops_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return list(dc_specs["services"].keys())


def _by_service_creation(service: dict[str, Any]) -> datetime:
    datetime_str = service["CreatedAt"]
    return arrow.get(datetime_str).datetime


@retry(
    stop=stop_after_delay(_MAX_WAIT_TIME),
    wait=wait_fixed(_WAIT_BEFORE_RETRY),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def _retrieve_started_services() -> list[dict[str, Any]]:
    expected_services = _core_services() + _ops_services()
    started_services: list[dict[str, Any]] = []
    async with aiodocker.Docker() as client:
        services_list = await client.services.list()

        started_services = sorted(
            (
                s
                for s in services_list
                if s["Spec"]["Name"].split("_")[-1] in expected_services
            ),
            key=_by_service_creation,
        )
        assert started_services, "no services started!"
        assert len(expected_services) == len(started_services), (
            "Some services are missing or unexpected:\n"
            f"expected: {len(expected_services)} {expected_services}\n"
            f"got: {len(started_services)} {[s['Spec']['Name'] for s in started_services]}"
        )
    return started_services


async def _check_service_status(
    service: dict[str, Any],
    service_statuses: dict[str, dict[str, Any]],
) -> bool:
    """Check service status and update the status dict. Returns True if service is ready."""
    async with aiodocker.Docker() as client:
        expected_replicas = (
            service["Spec"]["Mode"]["Replicated"]["Replicas"]
            if "Replicated" in service["Spec"]["Mode"]
            else len(await client.nodes.list())  # we are in global mode
        )
        service_name = service["Spec"]["Name"].split("_")[
            -1
        ]  # Get the actual service name

        # Get tasks for the service
        service_tasks: list[dict[str, Any]] = await client.tasks.list(
            filters={"service": service["Spec"]["Name"]}
        )

        running_replicas = sum(
            task["Status"]["State"] == _RUNNING_STATE for task in service_tasks
        )

        task_states = [task["Status"]["State"] for task in service_tasks]

        # Determine overall service state
        if running_replicas == expected_replicas:
            state = _RUNNING_STATE
        elif any(task["Status"]["State"] in _FAILED_STATES for task in service_tasks):
            state = "failed"
        else:
            state = "starting"

        # Calculate start time from running tasks
        start_time = None
        running_tasks = [
            task for task in service_tasks if task["Status"]["State"] == _RUNNING_STATE
        ]
        if running_tasks:
            # Calculate startup time from creation to running state
            startup_times = []
            for task in running_tasks:
                if "Timestamp" in task["Status"] and "CreatedAt" in task:
                    created_at = arrow.get(task["CreatedAt"]).datetime
                    started_at = arrow.get(task["Status"]["Timestamp"]).datetime
                    startup_time = (started_at - created_at).total_seconds()
                    startup_times.append(startup_time)

            if startup_times:
                # Use the average startup time for services with multiple replicas
                start_time = sum(startup_times) / len(startup_times)

        service_statuses[service_name] = {
            "state": state,
            "expected_replicas": expected_replicas,
            "running_replicas": running_replicas,
            "task_states": task_states,
            "start_time": start_time,
        }

        return running_replicas == expected_replicas


async def _wait_for_services() -> int:
    """Wait for all services to start and display progress with rich components."""
    _console.print(
        Panel.fit(
            "🚀 [bold blue]Waiting for osparc-simcore services to start...[/bold blue]",
            border_style="blue",
        )
    )

    started_services: list[dict[str, Any]] = await _retrieve_started_services()

    service_statuses: dict[str, dict[str, Any]] = {}
    global_start_time = time.time()

    # Initialize service statuses
    for service in started_services:
        service_name = service["Spec"]["Name"].split("_")[-1]
        service_statuses[service_name] = {
            "state": "starting",
            "expected_replicas": 0,
            "running_replicas": 0,
            "task_states": [],
            "start_time": None,
        }

    # Create progress bar
    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(complete_style="green"),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=_console,
    )

    task = progress.add_task("Started services...", total=len(started_services))

    @retry(
        stop=stop_after_delay(_MAX_WAIT_TIME),
        wait=wait_fixed(5),  # Wait 5 seconds between retries
        retry=retry_if_result(lambda result: not result),  # Retry if result is False
        before_sleep=before_sleep_log(_logger, logging.INFO),
    )
    async def _check_all_services_ready() -> bool:
        """Check if all services are ready and print status."""
        # Check status of all services
        ready_services = []
        for service in started_services:
            is_ready = await _check_service_status(service, service_statuses)
            if is_ready:
                ready_services.append(service)

        # Update progress
        progress.update(task, completed=len(ready_services))

        # Create and print the display elements
        table = _create_services_table(service_statuses)

        # Print services table
        _console.print(
            Panel(
                table,
                title="🐳 Docker Swarm Services Monitor",
                border_style="magenta",
            )
        )

        # Print overall progress
        _console.print(
            Panel(
                progress,
                title=f"⏱️  Overall Progress ({len(ready_services)}/{len(started_services)} services ready)",
                border_style="blue",
            )
        )

        # Return True if all services are ready, False otherwise
        return len(ready_services) == len(started_services)

    # Wait for all services to be ready
    await _check_all_services_ready()

    # Final summary
    total_time = time.time() - global_start_time
    _console.print(
        f"\n🎉 [bold green]All services are ready![/bold green] Total time: [bold]{total_time:.1f}s[/bold]"
    )

    return os.EX_OK


def main() -> None:
    try:
        asyncio.run(_wait_for_services())
    except KeyboardInterrupt as exc:
        _console.print("\n[red]❌ Operation cancelled by user[/red]")
        raise typer.Abort from exc
    except Exception as exc:
        _console.print(f"\n[red]❌ Error: {exc}[/red]")
        raise typer.Abort from exc


if __name__ == "__main__":
    typer.run(main)
