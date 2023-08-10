from enum import Enum

import typer
from models import Deployment
from portainer import check_containers_deploys, check_running_sidecars
from rich.console import Console
from settings import get_settings

console = Console()


class Action(str, Enum):
    containers = "containers"
    sidecars = "sidecars"


def main(deployment: Deployment, action: Action):
    settings = get_settings(deployment)
    console.print(f"Deployment: {deployment}")
    console.print(f"Action: {action}")

    if action == Action.containers:
        check_containers_deploys(settings, deployment)
    if action == Action.sidecars:
        check_running_sidecars(settings, deployment)


if __name__ == "__main__":
    typer.run(main)
