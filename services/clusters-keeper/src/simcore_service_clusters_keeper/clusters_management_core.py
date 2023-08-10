import datetime
import logging

from fastapi import FastAPI

from .core.settings import get_application_settings
from .models import EC2InstanceData
from .modules.ec2 import get_ec2_client
from .utils import ec2 as ec2_utils

_logger = logging.getLogger(__name__)


async def _find_terminateable_instances(
    app: FastAPI, gateways: list[EC2InstanceData]
) -> list[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec

    # get the corresponding ec2 instance data
    terminateable_instances: list[EC2InstanceData] = []

    for instance in gateways:
        # NOTE: AWS price is hourly based (e.g. same price for a machine used 2 minutes or 1 hour, so we wait until 55 minutes)
        elapsed_time_since_launched = (
            datetime.datetime.now(datetime.timezone.utc) - instance.launch_time
        )
        elapsed_time_since_full_hour = elapsed_time_since_launched % datetime.timedelta(
            hours=1
        )
        if (
            elapsed_time_since_full_hour
            >= app_settings.CLUSTERS_KEEPER_EC2_INSTANCES.EC2_INSTANCES_TIME_BEFORE_TERMINATION
        ):
            # let's terminate that one
            terminateable_instances.append(instance)

    if terminateable_instances:
        _logger.info(
            "the following nodes were found to be terminateable: '%s'",
            f"{[instance.id for instance in terminateable_instances]}",
        )
    return terminateable_instances


async def _get_running_gateways(app: FastAPI) -> list[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_EC2_INSTANCES  # nosec
    return await get_ec2_client(app).get_instances(
        app_settings.CLUSTERS_KEEPER_EC2_INSTANCES,
        ec2_utils.get_ec2_tags_for_listing(),
        state_names=["running"],
    )


async def _terminate_gateways(app: FastAPI, gateways: list[EC2InstanceData]) -> None:
    await get_ec2_client(app).terminate_instances(gateways)


async def check_clusters(app: FastAPI) -> None:
    gateways = await _get_running_gateways(app)
    if terminateable_gateways := await _find_terminateable_instances(app, gateways):
        await _terminate_gateways(app, terminateable_gateways)
