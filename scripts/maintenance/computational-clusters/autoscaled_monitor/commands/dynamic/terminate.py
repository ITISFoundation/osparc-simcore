"""``dynamic terminate`` — terminate dynamic EC2 instances."""

import asyncio
from typing import Annotated

import rich
import typer

from ... import analysis, ec2, rendering, utils
from ..._state import state
from ...models import AppState


async def _run(
    state: AppState,
    user_id: int | None,
    instance_id: str | None,
    *,
    force: bool,
) -> None:
    if not user_id and not instance_id:
        rich.print("either define user_id or instance_id!")
        raise typer.Exit(2)

    dynamic_instances = await ec2.list_dynamic_instances_from_ec2(
        state,
        filter_by_user_id=None,
        filter_by_wallet_id=None,
        filter_by_instance_id=instance_id,
    )
    dynamic_autoscaled_instances = await analysis.parse_dynamic_instances(
        state, dynamic_instances, state.ssh_key_path, user_id, None
    )

    if not dynamic_autoscaled_instances:
        rich.print("no instances found")
        raise typer.Exit(1)

    assert state.ec2_resource_autoscaling  # nosec
    rendering.print_dynamic_instances(
        dynamic_autoscaled_instances,
        state.environment,
        state.ec2_resource_autoscaling.meta.client.meta.region_name,
        output=None,
    )

    for instance in dynamic_autoscaled_instances:
        rich.print(
            f"terminating instance {instance.ec2_instance.instance_id} "
            f"with name {utils.get_instance_name(instance.ec2_instance)}"
        )
        if force is True or typer.confirm(
            f"Are you sure you want to terminate instance {instance.ec2_instance.instance_id}?"
        ):
            instance.ec2_instance.terminate()
            rich.print(f"terminated instance {instance.ec2_instance.instance_id}")
        else:
            rich.print("not terminating anything")


def terminate(
    user_id: Annotated[int | None, typer.Option(help="the user ID")] = None,
    instance_id: Annotated[str | None, typer.Option(help="the instance ID")] = None,
    *,
    force: Annotated[bool, typer.Option(help="will not ask for confirmation")] = False,
) -> None:
    """Terminate dynamic EC2 instance(s) for a given user or instance ID."""

    asyncio.run(_run(state, user_id, instance_id, force=force))
