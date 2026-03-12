"""``dynamic summary`` — verbose dynamic-instance details."""

import asyncio
from pathlib import Path
from typing import Annotated

import arrow
import rich
import typer

from ... import analysis, db, ec2, rendering
from ..._state import state
from ...models import AppState as _AppState
from ...models import DynamicInstance, DynamicServiceExtraInfo


def _collect_services(
    instances: list[DynamicInstance],
) -> list[tuple[int, str, str]]:
    """Collect (user_id, project_id, node_id) for all running services."""
    return [(svc.user_id, svc.project_id, svc.node_id) for inst in instances for svc in inst.running_services]


async def _run(
    state: "AppState",  # noqa: F821
    user_id: int | None,
    *,
    output_json: bool,
    output: Path | None,
) -> bool:
    assert isinstance(state, _AppState)
    assert state.ec2_resource_autoscaling

    dynamic_instances = await ec2.list_dynamic_instances_from_ec2(
        state,
        filter_by_user_id=user_id,
        filter_by_wallet_id=None,
        filter_by_instance_id=None,
    )
    dynamic_autoscaled_instances: list[DynamicInstance] = await analysis.parse_dynamic_instances(
        state, dynamic_instances, state.ssh_key_path, user_id, None
    )

    # Resolve user emails and wallet info from DB
    service_extra_info: dict[tuple[str, str], DynamicServiceExtraInfo] = {}
    services = _collect_services(dynamic_autoscaled_instances)
    if services:
        try:
            async with db.db_engine(state) as engine:
                service_extra_info = await db.get_dynamic_service_extra_info(engine, services)
        except Exception:  # pylint: disable=broad-exception-caught
            rich.print("[yellow]Warning: could not query DB for user/wallet info.[/yellow]")

    if output_json:
        rendering.print_summary_as_json(
            dynamic_autoscaled_instances,
            [],
            output=output,
        )
    else:
        rendering.print_dynamic_instances(
            dynamic_autoscaled_instances,
            state.environment,
            state.ec2_resource_autoscaling.meta.client.meta.region_name,
            output=output,
            service_extra_info=service_extra_info,
        )

    time_threshold = arrow.utcnow().shift(minutes=-30).datetime
    return not any(
        service.needs_manual_intervention and service.created_at < time_threshold
        for instance in dynamic_autoscaled_instances
        for service in instance.running_services
    )


def summary(
    *,
    user_id: Annotated[int, typer.Option(help="filters by the user ID")] = 0,
    as_json: Annotated[bool, typer.Option(help="outputs as json")] = False,
    output: Annotated[Path | None, typer.Option(help="outputs to a file")] = None,
) -> None:
    """Verbose view of dynamic autoscaled instances and their running services."""

    if not asyncio.run(
        _run(
            state,
            user_id or None,
            output_json=as_json,
            output=output,
        )
    ):
        raise typer.Exit(1)
