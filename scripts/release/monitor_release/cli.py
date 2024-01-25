from pathlib import Path
from typing import Annotated

import typer
from monitor_release.models import Deployment
from monitor_release.portainer import check_containers_deploys, check_running_sidecars
from monitor_release.settings import get_legacy_settings, get_release_settings
from rich.console import Console

app = typer.Typer()
console = Console()


EnvFileOption = typer.Option(
    exists=True,
    file_okay=True,
    dir_okay=False,
    writable=False,
    readable=True,
    resolve_path=True,
    help="Path to .env file",
)


@app.command()
def settings(
    env_file: Annotated[Path, EnvFileOption] = Path("repo.config"),
):
    settings_ = get_release_settings(env_file)
    console.print(settings_.model_dump_json(indent=1))


@app.command()
def containers(
    deployment: Deployment,
    env_file: Annotated[Path, EnvFileOption] = Path(".env"),
):
    settings_ = get_legacy_settings(f"{env_file}", deployment)
    console.print(f"Deployment: {deployment}")
    console.print("Action: containers")

    check_containers_deploys(settings_, deployment)


@app.command()
def sidecars(
    deployment: Deployment,
    env_file: Annotated[Path, EnvFileOption] = Path(".env"),
):
    settings_ = get_legacy_settings(f"{env_file}", deployment)
    console.print(f"Deployment: {deployment}")
    console.print("Action: sidecars")

    check_running_sidecars(settings_, deployment)
