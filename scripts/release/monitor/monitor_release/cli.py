from enum import Enum

import typer
from monitor_release.models import Deployment
from monitor_release.portainer import check_containers_deploys, check_running_sidecars
from monitor_release.settings import get_settings
from rich.console import Console

app = typer.Typer()
console = Console()


class Action(str, Enum):
    containers = "containers"
    sidecars = "sidecars"


@app.command()
def main(deployment: Deployment, action: Action):
    settings = get_settings(deployment)
    console.print(f"Deployment: {deployment}")
    console.print(f"Action: {action}")

    if action == Action.containers:
        check_containers_deploys(settings, deployment)
    if action == Action.sidecars:
        check_running_sidecars(settings, deployment)


# if __name__ == "__main__":
#     # main(Deployment.aws_staging, Action.containers)
#     typer.run(main)
