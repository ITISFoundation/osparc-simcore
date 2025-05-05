import asyncio
import os
from pathlib import Path
from typing import Annotated, Optional

import parse
import rich
import typer
from ansible.inventory.manager import InventoryManager
from ansible.parsing.dataloader import DataLoader
from dotenv import dotenv_values

from . import core as api
from .constants import (
    DEFAULT_COMPUTATIONAL_EC2_FORMAT,
    DEFAULT_COMPUTATIONAL_EC2_FORMAT_WORKERS,
    DEFAULT_DYNAMIC_EC2_FORMAT,
    DEPLOY_SSH_KEY_PARSER,
    UNIFIED_SSH_KEY_PARSE,
    wallet_id_spec,
)
from .ec2 import autoscaling_ec2_client, cluster_keeper_ec2_client
from .models import AppState, BastionHost

state: AppState = AppState(
    dynamic_parser=parse.compile(DEFAULT_DYNAMIC_EC2_FORMAT),
    computational_parser_primary=parse.compile(
        DEFAULT_COMPUTATIONAL_EC2_FORMAT, {"wallet_id_spec": wallet_id_spec}
    ),
    computational_parser_workers=parse.compile(
        DEFAULT_COMPUTATIONAL_EC2_FORMAT_WORKERS, {"wallet_id_spec": wallet_id_spec}
    ),
)

app = typer.Typer()


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
            f"[red]{inventory_path} invalid! Unable to find bastion_ip in the inventory file. TIP: Please run `make inventory` in {deploy_config} to generate it[/red]"
        )
        raise typer.Exit(os.EX_DATAERR) from err


@app.callback()
def main(
    deploy_config: Annotated[
        Path, typer.Option(help="path to the deploy configuration")
    ],
):
    """Manages external clusters"""

    state.deploy_config = deploy_config.expanduser()
    assert (
        deploy_config.is_dir()
    ), "deploy-config argument is not pointing to a directory!"
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

        if DEPLOY_SSH_KEY_PARSER.parse(
            f"{file_path.name}"
        ) is not None or UNIFIED_SSH_KEY_PARSE.parse(f"{file_path.name}"):
            rich.print(
                f"will be using following ssh_key_path: {file_path}. "
                "TIP: if wrong adapt the code or manually remove some of them."
            )
            state.ssh_key_path = file_path
            break
    if not state.ssh_key_path:
        rich.print(
            f"[red]could not find ssh key in {deploy_config}! Please run OPS code to generate it[/red]"
        )
        raise typer.Exit(1)


@app.command()
def summary(
    *,
    user_id: Annotated[int, typer.Option(help="filters by the user ID")] = 0,
    wallet_id: Annotated[int, typer.Option(help="filters by the wallet ID")] = 0,
    as_json: Annotated[bool, typer.Option(help="outputs as json")] = False,
    output: Annotated[Path | None, typer.Option(help="outputs to a file")] = None,
) -> None:
    """Show a summary of the current situation of autoscaled EC2 instances.

    Gives a list of all the instances used for dynamic services, and optionally shows what runs in them.
    Gives alist of all the instances used for computational services (e.g. primary + worker(s) instances)

    Arguments:
        repo_config -- path that shall point to a repo.config type of file (see osparc-ops-deployment-configuration repository)

    """

    if not asyncio.run(
        api.summary(
            state,
            user_id or None,
            wallet_id or None,
            output_json=as_json,
            output=output,
        )
    ):
        raise typer.Exit(1)


@app.command()
def cancel_jobs(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[
        Optional[int | None],  # noqa: UP007 # typer does not understand | syntax
        typer.Option(help="the wallet ID"),
    ] = None,
    *,
    abort_in_db: Annotated[
        bool,
        typer.Option(
            help="will also force the job to abort in the database (use only if job is in WAITING FOR CLUSTER/WAITING FOR RESOURCE)"
        ),
    ] = False,
) -> None:
    """Cancel jobs from the cluster, this will rely on osparc platform to work properly
    The director-v2 should receive the cancellation and abort the concerned pipelines in the next 15 seconds.
    NOTE: This should be called prior to clearing jobs on the cluster.

    Keyword Arguments:
        user_id -- the user ID
        wallet_id -- the wallet ID
        abort_in_db -- will also force the job to abort in the database (use only if job is in WAITING FOR CLUSTER/WAITING FOR RESOURCE)
    """
    asyncio.run(api.cancel_jobs(state, user_id, wallet_id, abort_in_db=abort_in_db))


@app.command()
def trigger_cluster_termination(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[
        Optional[int | None],  # noqa: UP007 # typer does not understand | syntax
        typer.Option(help="the wallet ID"),
    ] = None,
    *,
    force: Annotated[bool, typer.Option(help="will not ask for confirmation")] = False,
) -> None:
    """this will set the Heartbeat tag on the primary machine to 1 hour, thus ensuring the
    clusters-keeper will properly terminate that cluster.

    Keyword Arguments:
        user_id -- the user ID
        wallet_id -- the wallet ID
        force -- will not ask for confirmation (VERY RISKY! USE WITH CAUTION!)
    """
    asyncio.run(api.trigger_cluster_termination(state, user_id, wallet_id, force=force))


@app.command()
def check_database_connection() -> None:
    """this will check the connection to simcore database is ready"""
    asyncio.run(api.check_database_connection(state))


@app.command()
def terminate_dynamic_instances(
    user_id: Annotated[int | None, typer.Option(help="the user ID")] = None,
    instance_id: Annotated[str | None, typer.Option(help="the instance ID")] = None,
    *,
    force: Annotated[bool, typer.Option(help="will not ask for confirmation")] = False,
) -> None:
    """this will terminate the instance(s) used for the given user or instance ID."""
    asyncio.run(
        api.terminate_dynamic_instances(state, user_id, instance_id, force=force)
    )


if __name__ == "__main__":
    app()
