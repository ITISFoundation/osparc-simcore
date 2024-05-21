import datetime
import logging
from typing import Final, Iterable

import arrow
from aws_library.ec2.models import AWSTagKey, EC2InstanceData
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import parse_obj_as

from ..core.settings import get_application_settings
from ..modules.clusters import (
    delete_clusters,
    get_all_clusters,
    get_cluster_workers,
    set_instance_heartbeat,
)
from ..utils.dask import get_scheduler_auth, get_scheduler_url
from ..utils.ec2 import HEARTBEAT_TAG_KEY
from .dask import is_scheduler_busy, ping_scheduler

_logger = logging.getLogger(__name__)


def _get_instance_last_heartbeat(instance: EC2InstanceData) -> datetime.datetime:
    if last_heartbeat := instance.tags.get(HEARTBEAT_TAG_KEY, None):
        last_heartbeat_time: datetime.datetime = arrow.get(last_heartbeat).datetime
        return last_heartbeat_time
    launch_time: datetime.datetime = instance.launch_time
    return launch_time


_USER_ID_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "user_id")
_WALLET_ID_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "wallet_id")


async def _get_all_associated_worker_instances(
    app: FastAPI,
    primary_instances: Iterable[EC2InstanceData],
):
    worker_instances = []
    for instance in primary_instances:
        assert "user_id" in instance.tags  # nosec
        user_id = UserID(instance.tags[_USER_ID_TAG_KEY])
        assert "wallet_id" in instance.tags  # nosec
        # NOTE: wallet_id can be None
        wallet_id = (
            WalletID(instance.tags[_WALLET_ID_TAG_KEY])
            if instance.tags[_WALLET_ID_TAG_KEY] != "None"
            else None
        )

        worker_instances.extend(
            await get_cluster_workers(app, user_id=user_id, wallet_id=wallet_id)
        )
    return worker_instances


async def _find_terminateable_instances(
    app: FastAPI, instances: Iterable[EC2InstanceData]
) -> list[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES  # nosec

    # get the corresponding ec2 instance data
    terminateable_instances: list[EC2InstanceData] = []

    time_to_wait_before_termination = (
        app_settings.CLUSTERS_KEEPER_MAX_MISSED_HEARTBEATS_BEFORE_CLUSTER_TERMINATION
        * app_settings.SERVICE_TRACKING_HEARTBEAT
    )
    for instance in instances:
        last_heartbeat = _get_instance_last_heartbeat(instance)

        elapsed_time_since_heartbeat = (
            datetime.datetime.now(datetime.timezone.utc) - last_heartbeat
        )
        _logger.info(
            "%s has still %ss before being terminateable",
            f"{instance.id=}",
            f"{(time_to_wait_before_termination - elapsed_time_since_heartbeat).total_seconds()}",
        )
        if elapsed_time_since_heartbeat >= time_to_wait_before_termination:
            # let's terminate that one
            terminateable_instances.append(instance)

    # get all terminateable instances associated worker instances
    worker_instances = await _get_all_associated_worker_instances(
        app, terminateable_instances
    )

    return terminateable_instances + worker_instances


async def check_clusters(app: FastAPI) -> None:
    instances = await get_all_clusters(app)

    # analyse connected clusters (e.g. normal function)
    connected_intances = [
        instance
        for instance in instances
        if await ping_scheduler(get_scheduler_url(instance), get_scheduler_auth(app))
    ]
    for instance in connected_intances:
        is_busy = await is_scheduler_busy(
            get_scheduler_url(instance), get_scheduler_auth(app)
        )
        _logger.info(
            "%s currently %s",
            f"{instance.id=} for {instance.tags=}",
            f"{'is running tasks' if is_busy else 'not doing anything!'}",
        )
        if is_busy:
            await set_instance_heartbeat(app, instance=instance)
    if terminateable_instances := await _find_terminateable_instances(
        app, connected_intances
    ):
        await delete_clusters(app, instances=terminateable_instances)

    # analyse disconnected instances (currently starting or broken)
    disconnected_instances = set(instances) - set(connected_intances)
    if terminateable_instances := await _find_terminateable_instances(
        app, disconnected_instances
    ):
        _logger.error(
            "The following clusters'primary EC2 were found as unresponsive and will be terminated: '%s",
            f"{[i.id for i in terminateable_instances]}",
        )
        await delete_clusters(app, instances=terminateable_instances)
