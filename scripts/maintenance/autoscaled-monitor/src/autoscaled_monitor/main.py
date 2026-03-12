"""CLI entry-point — one file per command, aggregated via group apps."""

import os
from pathlib import Path
from typing import Annotated

import parse
import rich
import typer
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from dotenv import dotenv_values

from ._state import state
from .commands.computational.cancel_jobs import cancel_jobs as comp_cancel_jobs_cmd
from .commands.computational.summary import summary as comp_summary_cmd
from .commands.computational.terminate import terminate as comp_terminate_cmd
from .commands.db.check import check as db_check_cmd
from .commands.dynamic.summary import summary as dyn_summary_cmd
from .commands.dynamic.terminate import terminate as dyn_terminate_cmd
from .commands.summary import summary as top_summary_cmd
from .constants import (
    DEFAULT_COMPUTATIONAL_EC2_FORMAT,
    DEFAULT_COMPUTATIONAL_EC2_FORMAT_WORKERS,
    DEPLOY_SSH_KEY_PARSER,
    UNIFIED_SSH_KEY_PARSE,
    wallet_id_spec,
)
from .ec2 import autoscaling_ec2_client, cluster_keeper_ec2_client
from .models import BastionHost

# ---------------------------------------------------------------------------
# Root Typer app
# ---------------------------------------------------------------------------
app = typer.Typer(pretty_exceptions_enable=False)

# --- Top-level commands ---
app.command("summary")(top_summary_cmd)

# --- Sub-command groups ---
dynamic_app = typer.Typer(help="Dynamic autoscaled instances")
dynamic_app.command("summary")(dyn_summary_cmd)
dynamic_app.command("terminate")(dyn_terminate_cmd)

computational_app = typer.Typer(help="Computational clusters")
computational_app.command("summary")(comp_summary_cmd)
computational_app.command("cancel-jobs")(comp_cancel_jobs_cmd)
computational_app.command("terminate")(comp_terminate_cmd)

db_app = typer.Typer(help="Database utilities")
db_app.command("check")(db_check_cmd)

app.add_typer(dynamic_app, name="dynamic")
app.add_typer(computational_app, name="computational")
app.add_typer(db_app, name="db")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_repo_config(deploy_config: Path) -> dict[str, str | None]:
    repo_config = deploy_config / "repo.config"
    if not repo_config.exists():
        rich.print(
            f"[red]{repo_config} does not exist! Please run `make repo.config` in {deploy_config} to generate it[/red]"
        )
        raise typer.Exit(os.EX_DATAERR)

    environment = dotenv_values(repo_config)
    assert environment
    return environment


def _parse_inventory(deploy_config: Path) -> BastionHost:
    inventory_path = deploy_config / "ansible" / "inventory.ini"
    if not inventory_path.exists():
        rich.print(
            f"[red]{inventory_path} does not exist! Please run `make inventory` in {deploy_config} to generate it[/red]"
        )
        raise typer.Exit(os.EX_DATAERR)

    loader = DataLoader()
    inventory = InventoryManager(loader=loader, sources=[f"{inventory_path}"])

    try:
        return BastionHost(
            ip=inventory.groups["CAULDRON_UNIX"].get_vars()["bastion_ip"],
            user_name=inventory.groups["CAULDRON_UNIX"].get_vars()["bastion_user"],
        )
    except KeyError as err:
        rich.print(
            f"[red]{inventory_path} invalid! Unable to find bastion_ip in the inventory file. "
            f"TIP: Please run `make inventory` in {deploy_config} to generate it[/red]"
        )
        raise typer.Exit(os.EX_DATAERR) from err


# ---------------------------------------------------------------------------
# Callback — shared initialisation
# ---------------------------------------------------------------------------


@app.callback()
def main(
    deploy_config: Annotated[Path, typer.Option(help="path to the deploy configuration")],
) -> None:
    """Manages external clusters"""

    state.deploy_config = deploy_config.expanduser()
    assert deploy_config.is_dir(), "deploy-config argument is not pointing to a directory!"
    state.environment = _parse_repo_config(deploy_config)
    state.main_bastion_host = _parse_inventory(deploy_config)

    # connect to ec2s
    state.ec2_resource_autoscaling = autoscaling_ec2_client(state)
    state.ec2_resource_clusters_keeper = cluster_keeper_ec2_client(state)

    assert state.environment["EC2_INSTANCES_KEY_NAME"]
    dynamic_pattern = f"{state.environment['EC2_INSTANCES_NAME_PREFIX']}-{{key_name}}"
    state.dynamic_parser = parse.compile(dynamic_pattern)
    if state.environment["CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX"]:
        state.computational_parser_primary = parse.compile(
            rf"{state.environment['CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX'].strip('-')}-{DEFAULT_COMPUTATIONAL_EC2_FORMAT}",
            {"wallet_id_spec": wallet_id_spec},
        )
        state.computational_parser_workers = parse.compile(
            rf"{state.environment['CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX'].strip('-')}-{DEFAULT_COMPUTATIONAL_EC2_FORMAT_WORKERS}",
            {"wallet_id_spec": wallet_id_spec},
        )

    # locate ssh key path
    for file_path in deploy_config.glob("**/*.pem"):
        if any(_ in file_path.name for _ in ["license", "pkcs8", "dask"]):
            continue
        if DEPLOY_SSH_KEY_PARSER.parse(f"{file_path.name}") is not None or UNIFIED_SSH_KEY_PARSE.parse(
            f"{file_path.name}"
        ):
            rich.print(f"[dim]SSH key: {file_path}[/dim]")
            state.ssh_key_path = file_path
            break
    if not state.ssh_key_path:
        rich.print(f"[red]could not find ssh key in {deploy_config}! Please run OPS code to generate it[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
