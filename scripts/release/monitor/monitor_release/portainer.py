from models import RunningSidecar
from portainer_utils import (
    check_simcore_deployed_services,
    check_simcore_running_sidecars,
    get_bearer_token,
    get_containers,
    get_services,
    get_tasks,
)
from rich.console import Console
from rich.table import Table

console = Console()


def check_containers_deploys(settings, deployment):
    token = get_bearer_token(settings)
    services = get_services(settings, token)
    tasks = get_tasks(settings, token)
    containers = get_containers(settings, token)

    output = check_simcore_deployed_services(settings, services, tasks, containers)

    table = Table(
        "Service",
        "Status",
        "Last Updated",
        "Git SHA",
        title=f"[bold yellow]{deployment.upper()}[/bold yellow]",
    )
    for item in output.values():
        service_name = item["service_name"]
        container_status = "[bold red]Not running[/bold red]"
        container_timestamp = None
        container_git_sha = None
        for task in item["tasks"]:
            oldest_running_task_timestamp = None
            if task["status"] == "running":
                if (
                    oldest_running_task_timestamp is None
                    or oldest_running_task_timestamp > task["timestamp"]
                ):
                    container_status = f"[green]{task['status']}[/green]"
                    container_timestamp = f"{task['timestamp']}"
                    container_git_sha = task["git_sha"]

                    oldest_running_task_timestamp = task["timestamp"]
            if task["status"] == "starting":
                container_status = f"[blue]{task['status']}[/blue]"
                container_timestamp = f"{task['timestamp']}"
                container_git_sha = task["git_sha"]
                break

        table.add_row(
            service_name, container_status, container_timestamp, container_git_sha
        )

    console.print(table)


def check_running_sidecars(settings, deployment):
    token = get_bearer_token(settings)
    services = get_services(settings, token)

    sidecars: list[RunningSidecar] = check_simcore_running_sidecars(settings, services)
    table = Table(
        "Sidecar name",
        "Created at",
        "User ID",
        "Project ID",
        "Service Key",
        "Service Version",
        title=f"[bold yellow]{deployment.upper()}[/bold yellow]",
    )
    for sidecar in sidecars:
        table.add_row(
            sidecar.name,
            f"{sidecar.created_at}",
            sidecar.user_id,
            sidecar.project_id,
            sidecar.service_key,
            sidecar.service_version,
        )

    console.print(table)
