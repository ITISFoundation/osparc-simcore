import datetime
import logging

import arrow
from fastapi import FastAPI

from ..core.settings import get_application_settings
from ..models import EC2InstanceData
from ..modules.clusters import delete_clusters, get_all_clusters
from ..utils.ec2 import HEARTBEAT_TAG_KEY

_logger = logging.getLogger(__name__)


def _get_instance_last_heartbeat(instance: EC2InstanceData) -> datetime.datetime:
    if last_heartbeat := instance.tags.get(HEARTBEAT_TAG_KEY, None):
        return arrow.get(last_heartbeat).datetime
    return instance.launch_time


async def _find_terminateable_instances(
    app: FastAPI, instances: list[EC2InstanceData]
) -> list[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec

    # get the corresponding ec2 instance data
    terminateable_instances: list[EC2InstanceData] = []

    for instance in instances:
        last_heartbeat = _get_instance_last_heartbeat(instance)

        elapsed_time_since_heartbeat = (
            datetime.datetime.now(datetime.timezone.utc) - last_heartbeat
        )

        if elapsed_time_since_heartbeat >= (
            app_settings.CLUSTERS_KEEPER_MAX_MISSED_HEARTBEATS_BEFORE_CLUSTER_TERMINATION
            * app_settings.SERVICE_TRACKING_HEARTBEAT
        ):
            # let's terminate that one
            terminateable_instances.append(instance)

    return terminateable_instances


async def check_clusters(app: FastAPI) -> None:
    instances = await get_all_clusters(app)
    if terminateable_instances := await _find_terminateable_instances(app, instances):
        await delete_clusters(app, instances=terminateable_instances)
