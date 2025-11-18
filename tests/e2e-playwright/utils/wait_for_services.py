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
from rich.live import Live
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table
from tenacity import retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

# Configure logging to be less verbose for prettier output
logging.basicConfig(level=logging.ERROR)
_logger = logging.getLogger(__name__)

console = Console()

_current_dir = (
    Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent
)

WAIT_BEFORE_RETRY = 10
MAX_WAIT_TIME = 5 * 60

# SEE https://docs.docker.com/engine/swarm/how-swarm-mode-works/swarm-task-states/

PRE_STATES = [
    "new",  # The task was initialized.
    "pending",  # Resources for the task were allocated.
    "assigned",  # Docker assigned the task to nodes.
    "accepted",  # The task was accepted by a worker node. If a worker node rejects the task, the state changes to REJECTED.
    "preparing",  # Docker is preparing the task.
    "starting",  # Docker is starting the task.
]

RUNNING_STATE = "running"  # The task is executing.

FAILED_STATES = [
    "complete",  # The task exited without an error code.
    "failed",  # The task exited with an error code.
    "shutdown",  # Docker requested the task to shut down.
    "rejected",  # The worker node rejected the task.
    "orphaned",  # The node was down for too long.
    "remove",  # The task is not terminal but the associated service was removed or scaled down.
]


def get_status_emoji_and_color(state: str) -> tuple[str, str]:
    """Get emoji and color for service state."""
    if state == RUNNING_STATE:
        return "✅", "green"
    if state in PRE_STATES:
        return "🔄", "yellow"
    if state in FAILED_STATES:
        return "❌", "red"
    return "❓", "white"


def create_services_table(service_statuses: dict[str, dict[str, Any]]) -> Table:
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
        emoji, color = get_status_emoji_and_color(status["state"])

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
                emoji, _ = get_status_emoji_and_color(state)
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


def osparc_simcore_root_dir() -> Path:
    WILDCARD = "services/web/server"

    root_dir = Path(_current_dir)
    while not any(root_dir.glob(WILDCARD)) and root_dir != Path("/"):
        root_dir = root_dir.parent

    msg = f"'{root_dir}' does not look like the git root directory of osparc-simcore"
    assert root_dir.exists(), msg
    assert any(root_dir.glob(WILDCARD)), msg
    assert any(root_dir.glob(".git")), msg

    return root_dir


def core_docker_compose_file() -> Path:
    stack_files = list(osparc_simcore_root_dir().glob(".stack-simcore*"))
    assert stack_files
    return stack_files[0]


def core_services() -> list[str]:
    with core_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return list(dc_specs["services"].keys())


def ops_docker_compose_file() -> Path:
    return osparc_simcore_root_dir() / ".stack-ops.yml"


def ops_services() -> list[str]:
    with ops_docker_compose_file().open() as fp:
        dc_specs = yaml.safe_load(fp)
        return list(dc_specs["services"].keys())


def _by_service_creation(service: dict[str, Any]) -> datetime:
    datetime_str = service["CreatedAt"]
    return arrow.get(datetime_str).datetime


@retry(
    stop=stop_after_delay(MAX_WAIT_TIME),
    wait=wait_fixed(WAIT_BEFORE_RETRY),
    before_sleep=before_sleep_log(_logger, logging.WARNING),
)
async def _retrieve_started_services() -> list[dict[str, Any]]:
    expected_services = core_services() + ops_services()
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
    start_times: dict[str, float],
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
            task["Status"]["State"] == RUNNING_STATE for task in service_tasks
        )

        task_states = [task["Status"]["State"] for task in service_tasks]

        # Determine overall service state
        if running_replicas == expected_replicas:
            state = RUNNING_STATE
            if service_name not in start_times:
                start_times[service_name] = time.time()
        elif any(task["Status"]["State"] in FAILED_STATES for task in service_tasks):
            state = "failed"
        else:
            state = "starting"

        # Calculate start time
        start_time = None
        if service_name in start_times:
            start_time = time.time() - start_times[service_name]

        service_statuses[service_name] = {
            "state": state,
            "expected_replicas": expected_replicas,
            "running_replicas": running_replicas,
            "task_states": task_states,
            "start_time": start_time,
        }

        return running_replicas == expected_replicas


async def wait_for_services() -> int:
    """Wait for all services to start and display progress in a beautiful table."""
    console.print(
        Panel.fit(
            "🚀 [bold blue]Waiting for osparc-simcore services to start[/bold blue]",
            border_style="blue",
        )
    )

    started_services: list[dict[str, Any]] = await _retrieve_started_services()

    service_statuses: dict[str, dict[str, Any]] = {}
    start_times: dict[str, float] = {}
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
        console=console,
        transient=False,
    )

    with Live(console=console, refresh_per_second=2) as live:
        task = progress.add_task("Starting services...", total=len(started_services))

        while True:
            # Check status of all services
            ready_services = []
            for service in started_services:
                is_ready = await _check_service_status(
                    service, service_statuses, start_times
                )
                if is_ready:
                    ready_services.append(service)

            # Update progress
            progress.update(task, completed=len(ready_services))

            # Create the display
            table = create_services_table(service_statuses)

            # Add overall progress
            overall_progress = Panel(
                progress,
                title=f"⏱️  Overall Progress ({len(ready_services)}/{len(started_services)} services ready)",
                border_style="blue",
            )

            # Display both
            live.update(
                Panel(
                    f"{overall_progress}\n\n{table}",
                    title="Docker Swarm Services Monitor",
                )
            )

            # Check if all services are ready
            if len(ready_services) == len(started_services):
                break

            await asyncio.sleep(2)

    # Final summary
    total_time = time.time() - global_start_time
    console.print(
        f"\n🎉 [bold green]All services are ready![/bold green] Total time: [bold]{total_time:.1f}s[/bold]"
    )

    # Create final summary table
    final_table = Table(
        title="🏁 Final Service Startup Summary",
        show_header=True,
        header_style="bold green",
    )
    final_table.add_column("Service", style="cyan")
    final_table.add_column("Startup Time", justify="right", style="green")
    final_table.add_column("Status", justify="center")

    # Sort by startup time
    sorted_services = sorted(
        service_statuses.items(), key=lambda x: x[1]["start_time"] or 0
    )

    for service_name, status in sorted_services:
        emoji, _ = get_status_emoji_and_color(status["state"])
        start_time_text = (
            f"{status['start_time']:.1f}s"
            if status["start_time"] is not None
            else "N/A"
        )
        final_table.add_row(service_name, start_time_text, f"{emoji} {status['state']}")

    console.print(final_table)

    return os.EX_OK


def main() -> int:
    """Main entry point for the script."""
    try:
        return asyncio.run(wait_for_services())
    except KeyboardInterrupt:
        console.print("\n[red]❌ Operation cancelled by user[/red]")
        return 1
    except Exception as exc:
        console.print(f"\n[red]❌ Error: {exc}[/red]")
        return 1


if __name__ == "__main__":
    typer.run(main)
