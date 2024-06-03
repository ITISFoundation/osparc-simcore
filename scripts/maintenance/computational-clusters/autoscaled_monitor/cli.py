import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Final

import boto3
import parse
import rich
import typer
from dotenv import dotenv_values
from mypy_boto3_ec2 import EC2ServiceResource

from . import osparc_clusters as api

DEFAULT_COMPUTATIONAL_EC2_FORMAT: Final[
    str
] = r"osparc-computational-cluster-{role}-{swarm_stack_name}-user_id:{user_id:d}-wallet_id:{wallet_id:d}"
DEFAULT_DYNAMIC_EC2_FORMAT: Final[str] = r"osparc-dynamic-autoscaled-worker-{key_name}"
DEPLOY_SSH_KEY_PARSER: Final[parse.Parser] = parse.compile(r"osparc-{random_name}.pem")


@dataclass(kw_only=True)
class AppState:
    environment: dict[str, str | None] = field(default_factory=dict)
    ec2_resource_autoscaling: EC2ServiceResource | None = None
    ec2_resource_clusters_keeper: EC2ServiceResource | None = None
    dynamic_parser: parse.Parser
    computational_parser: parse.Parser
    deploy_config: Path | None = None
    ssh_key_path: Path | None = None


state: AppState = AppState(
    dynamic_parser=parse.compile(DEFAULT_DYNAMIC_EC2_FORMAT),
    computational_parser=parse.compile(DEFAULT_COMPUTATIONAL_EC2_FORMAT),
)

app = typer.Typer()


def _parse_environment(deploy_config: Path) -> dict[str, str | None]:
    repo_config = deploy_config / "repo.config"
    assert repo_config.exists()
    environment = dotenv_values(repo_config)
    if environment["AUTOSCALING_EC2_ACCESS_KEY_ID"] == "":
        rich.print(
            "Terraform variables detected, looking for repo.config.frozen as alternative."
            " TIP: you are responsible for them being up to date!!"
        )
        repo_config = deploy_config / "repo.config.frozen"
        assert repo_config.exists()
        environment = dotenv_values(repo_config)

        if environment["AUTOSCALING_EC2_ACCESS_KEY_ID"] == "":
            error_msg = (
                "Terraform is necessary in order to check into that deployment!\n"
                f"install terraform (check README.md in {state.deploy_config} for instructions)"
                "then run make repo.config.frozen, then re-run this code"
            )
            rich.print(error_msg)
            raise typer.Abort(error_msg)
    assert environment
    return environment


@app.callback()
def main(
    deploy_config: Annotated[
        Path, typer.Option(help="path to the deploy configuration")
    ]
):
    """Manages external clusters"""

    state.deploy_config = deploy_config.expanduser()
    assert (
        deploy_config.is_dir()
    ), "deploy-config argument is not pointing to a directory!"

    state.environment = _parse_environment(deploy_config)

    # connect to ec2s
    state.ec2_resource_autoscaling = boto3.resource(
        "ec2",
        region_name=state.environment["AUTOSCALING_EC2_REGION_NAME"],
        aws_access_key_id=state.environment["AUTOSCALING_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment["AUTOSCALING_EC2_SECRET_ACCESS_KEY"],
    )

    state.ec2_resource_clusters_keeper = boto3.resource(
        "ec2",
        region_name=state.environment["CLUSTERS_KEEPER_EC2_REGION_NAME"],
        aws_access_key_id=state.environment["CLUSTERS_KEEPER_EC2_ACCESS_KEY_ID"],
        aws_secret_access_key=state.environment[
            "CLUSTERS_KEEPER_EC2_SECRET_ACCESS_KEY"
        ],
    )

    assert state.environment["EC2_INSTANCES_KEY_NAME"]
    state.dynamic_parser = parse.compile(
        f"{state.environment['EC2_INSTANCES_NAME_PREFIX']}-{{key_name}}"
    )
    if state.environment["CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX"]:
        state.computational_parser = parse.compile(
            f"{state.environment['CLUSTERS_KEEPER_EC2_INSTANCES_PREFIX']}-{DEFAULT_COMPUTATIONAL_EC2_FORMAT}"
        )

    # locate ssh key path
    for file_path in deploy_config.glob("**/*.pem"):
        # very bad HACK
        if (
            any(_ in f"{file_path}" for _ in ("sim4life.io", "osparc-master"))
            and "openssh" not in f"{file_path}"
        ):
            continue

        if DEPLOY_SSH_KEY_PARSER.parse(f"{file_path.name}") is not None:
            rich.print(
                f"will be using following ssh_key_path: {file_path}. "
                "TIP: if wrong adapt the code or manually remove some of them."
            )
            state.ssh_key_path = file_path
            break


@app.command()
def summary(
    user_id: Annotated[int, typer.Option(help="filters by the user ID")] = 0,
    wallet_id: Annotated[int, typer.Option(help="filters by the wallet ID")] = 0,
) -> None:
    """Show a summary of the current situation of autoscaled EC2 instances.

    Gives a list of all the instances used for dynamic services, and optionally shows what runs in them.
    Gives alist of all the instances used for computational services (e.g. primary + worker(s) instances)

    Arguments:
        repo_config -- path that shall point to a repo.config type of file (see osparc-ops-deployment-configuration repository)

    """

    asyncio.run(api.summary(user_id or None, wallet_id or None))


@app.command()
def cancel_jobs(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int, typer.Option(help="the wallet ID")],
    *,
    force: Annotated[
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
    """
    asyncio.run(api.cancel_jobs(user_id, wallet_id, force=force))


@app.command()
def trigger_cluster_termination(
    user_id: Annotated[int, typer.Option(help="the user ID")],
    wallet_id: Annotated[int, typer.Option(help="the wallet ID")],
) -> None:
    """this will set the Heartbeat tag on the primary machine to 1 hour, thus ensuring the
    clusters-keeper will properly terminate that cluster.

    Keyword Arguments:
        user_id -- the user ID
        wallet_id -- the wallet ID
    """
    asyncio.run(api.trigger_cluster_termination(user_id, wallet_id))


if __name__ == "__main__":
    app()
