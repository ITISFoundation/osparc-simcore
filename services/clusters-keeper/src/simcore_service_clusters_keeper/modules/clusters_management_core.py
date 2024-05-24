import datetime
import logging
from collections.abc import Iterable
from typing import Final

import arrow
from aws_library.ec2.models import AWSTagKey, EC2InstanceData
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import parse_obj_as
from servicelib.logging_utils import log_catch

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


def _get_instance_last_heartbeat(instance: EC2InstanceData) -> datetime.datetime | None:
    if last_heartbeat := instance.tags.get(
        HEARTBEAT_TAG_KEY,
    ):
        last_heartbeat_time: datetime.datetime = arrow.get(last_heartbeat).datetime
        return last_heartbeat_time

    return None


_USER_ID_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "user_id")
_WALLET_ID_TAG_KEY: Final[AWSTagKey] = parse_obj_as(AWSTagKey, "wallet_id")


async def _get_all_associated_worker_instances(
    app: FastAPI,
    primary_instances: Iterable[EC2InstanceData],
) -> list[EC2InstanceData]:
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
    startup_delay = (
        app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_MAX_START_TIME
    )
    for instance in instances:
        if last_heartbeat := _get_instance_last_heartbeat(instance):
            elapsed_time_since_heartbeat = arrow.utcnow().datetime - last_heartbeat
            allowed_time_to_wait = time_to_wait_before_termination
            if elapsed_time_since_heartbeat >= allowed_time_to_wait:
                terminateable_instances.append(instance)
            else:
                _logger.info(
                    "%s has still %ss before being terminateable",
                    f"{instance.id=}",
                    f"{(allowed_time_to_wait - elapsed_time_since_heartbeat).total_seconds()}",
                )
        else:
            elapsed_time_since_startup = arrow.utcnow().datetime - instance.launch_time
            allowed_time_to_wait = startup_delay
            if elapsed_time_since_startup >= allowed_time_to_wait:
                terminateable_instances.append(instance)

    # get all terminateable instances associated worker instances
    worker_instances = await _get_all_associated_worker_instances(
        app, terminateable_instances
    )

    return terminateable_instances + worker_instances


async def check_clusters(app: FastAPI) -> None:
    primary_instances = await get_all_clusters(app)

    connected_intances = {
        instance
        for instance in primary_instances
        if await ping_scheduler(get_scheduler_url(instance), get_scheduler_auth(app))
    }

    for instance in connected_intances:
        with log_catch(_logger, reraise=False):
            # NOTE: some connected instance could in theory break between these 2 calls, therefore this is silenced and will
            # be handled in the next call to check_clusters
            if await is_scheduler_busy(
                get_scheduler_url(instance), get_scheduler_auth(app)
            ):
                _logger.info(
                    "%s is running tasks",
                    f"{instance.id=} for {instance.tags=}",
                )
                await set_instance_heartbeat(app, instance=instance)
    if terminateable_instances := await _find_terminateable_instances(
        app, connected_intances
    ):
        await delete_clusters(app, instances=terminateable_instances)

    # analyse disconnected instances (currently starting or broken)
    disconnected_instances = primary_instances - connected_intances

    # starting instances do not have a heartbeat set but sometimes might fail and should be terminated
    starting_instances = {
        instance
        for instance in disconnected_instances
        if _get_instance_last_heartbeat(instance) is None
    }

    if terminateable_instances := await _find_terminateable_instances(
        app, starting_instances
    ):
        _logger.warning(
            "The following clusters'primary EC2 were starting for too long and will be terminated now "
            "(either because a cluster was started and is not needed anymore, or there is an issue): '%s",
            f"{[i.id for i in terminateable_instances]}",
        )
        await delete_clusters(app, instances=terminateable_instances)

    # the other instances are broken (they were at some point connected but now not anymore)
    broken_instances = disconnected_instances - starting_instances
    if terminateable_instances := await _find_terminateable_instances(
        app, broken_instances
    ):
        _logger.error(
            "The following clusters'primary EC2 were found as unresponsive "
            "(TIP: there is something wrong here, please inform support) and will be terminated now: '%s",
            f"{[i.id for i in terminateable_instances]}",
        )
        await delete_clusters(app, instances=terminateable_instances)
