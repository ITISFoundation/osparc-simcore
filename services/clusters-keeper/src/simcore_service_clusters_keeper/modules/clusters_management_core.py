import datetime
import logging

import arrow
from fastapi import FastAPI

from ..core.settings import get_application_settings
from ..models import EC2InstanceData
from ..modules.clusters import delete_clusters, get_all_clusters, set_instance_heartbeat
from ..utils.dask import get_gateway_authentication, get_gateway_url
from ..utils.ec2 import HEARTBEAT_TAG_KEY, get_user_id_from_tags
from .dask import is_gateway_busy, ping_gateway

_logger = logging.getLogger(__name__)


def _get_instance_last_heartbeat(instance: EC2InstanceData) -> datetime.datetime:
    if last_heartbeat := instance.tags.get(HEARTBEAT_TAG_KEY, None):
        last_heartbeat_time: datetime.datetime = arrow.get(last_heartbeat).datetime
        return last_heartbeat_time
    return instance.launch_time


async def _find_terminateable_instances(
    app: FastAPI, instances: list[EC2InstanceData]
) -> list[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec

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

    return terminateable_instances


async def check_clusters(app: FastAPI) -> None:
    instances = await get_all_clusters(app)
    app_settings = get_application_settings(app)
    connected_intances = [
        instance
        for instance in instances
        if await ping_gateway(
            url=get_gateway_url(instance),
            password=app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_GATEWAY_PASSWORD,
        )
    ]
    for instance in connected_intances:
        is_busy = await is_gateway_busy(
            url=get_gateway_url(instance),
            gateway_auth=get_gateway_authentication(
                user_id=get_user_id_from_tags(instance.tags),
                password=app_settings.CLUSTERS_KEEPER_COMPUTATIONAL_BACKEND_GATEWAY_PASSWORD,
            ),
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
