import datetime
import logging
from collections.abc import Iterable
from typing import Final

import arrow
from aws_library.ec2 import AWSTagKey, EC2InstanceData
from aws_library.ec2._models import AWSTagValue
from fastapi import FastAPI
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import TypeAdapter
from servicelib.logging_utils import log_catch
from servicelib.utils import limited_gather

from ..constants import (
    DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY,
    DOCKER_STACK_DEPLOY_COMMAND_NAME,
    ROLE_TAG_KEY,
    USER_ID_TAG_KEY,
    WALLET_ID_TAG_KEY,
    WORKER_ROLE_TAG_VALUE,
)
from ..core.settings import get_application_settings
from ..modules.clusters import (
    delete_clusters,
    get_all_clusters,
    get_cluster_workers,
    set_instance_heartbeat,
)
from ..utils.clusters import create_deploy_cluster_stack_script
from ..utils.dask import get_scheduler_auth, get_scheduler_url
from ..utils.ec2 import (
    HEARTBEAT_TAG_KEY,
    get_cluster_name,
    user_id_from_instance_tags,
    wallet_id_from_instance_tags,
)
from .dask import is_scheduler_busy, ping_scheduler
from .ec2 import get_ec2_client
from .ssm import get_ssm_client

_logger = logging.getLogger(__name__)


def _get_instance_last_heartbeat(instance: EC2InstanceData) -> datetime.datetime | None:
    if last_heartbeat := instance.tags.get(
        HEARTBEAT_TAG_KEY,
    ):
        last_heartbeat_time: datetime.datetime = arrow.get(last_heartbeat).datetime
        return last_heartbeat_time

    return None


_USER_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("user_id")
_WALLET_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "wallet_id"
)


async def _get_all_associated_worker_instances(
    app: FastAPI,
    primary_instances: Iterable[EC2InstanceData],
) -> set[EC2InstanceData]:
    worker_instances: set[EC2InstanceData] = set()
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

        worker_instances.update(
            await get_cluster_workers(app, user_id=user_id, wallet_id=wallet_id)
        )
    return worker_instances


async def _find_terminateable_instances(
    app: FastAPI, instances: Iterable[EC2InstanceData]
) -> set[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES  # nosec

    # get the corresponding ec2 instance data
    terminateable_instances: set[EC2InstanceData] = set()

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
                terminateable_instances.add(instance)
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
                terminateable_instances.add(instance)

    # get all terminateable instances associated worker instances
    worker_instances = await _get_all_associated_worker_instances(
        app, terminateable_instances
    )

    return terminateable_instances.union(worker_instances)


async def check_clusters(app: FastAPI) -> None:
    primary_instances = await get_all_clusters(app)

    connected_intances = {
        instance
        for instance in primary_instances
        if await ping_scheduler(get_scheduler_url(instance), get_scheduler_auth(app))
    }

    # set intance heartbeat if scheduler is busy
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
    # clean any cluster that is not doing anything
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
    # remove instances that were starting for too long
    if terminateable_instances := await _find_terminateable_instances(
        app, starting_instances
    ):
        _logger.warning(
            "The following clusters'primary EC2 were starting for too long and will be terminated now "
            "(either because a cluster was started and is not needed anymore, or there is an issue): '%s",
            f"{[i.id for i in terminateable_instances]}",
        )
        await delete_clusters(app, instances=terminateable_instances)

    # NOTE: transmit command to start docker swarm/stack if needed
    # once the instance is connected to the SSM server,
    # use ssm client to send the command to these instances,
    # we send a command that contain:
    # the docker-compose file in binary,
    # the call to init the docker swarm and the call to deploy the stack
    instances_in_need_of_deployment = {
        i
        for i in starting_instances - terminateable_instances
        if DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY not in i.tags
    }

    if instances_in_need_of_deployment:
        app_settings = get_application_settings(app)
        ssm_client = get_ssm_client(app)
        ec2_client = get_ec2_client(app)
        instances_in_need_of_deployment_ssm_connection_state = await limited_gather(
            *[
                ssm_client.is_instance_connected_to_ssm_server(i.id)
                for i in instances_in_need_of_deployment
            ],
            reraise=False,
            log=_logger,
            limit=20,
        )
        ec2_connected_to_ssm_server = [
            i
            for i, c in zip(
                instances_in_need_of_deployment,
                instances_in_need_of_deployment_ssm_connection_state,
                strict=True,
            )
            if c is True
        ]
        started_instances_ready_for_command = ec2_connected_to_ssm_server
        if started_instances_ready_for_command:
            # we need to send 1 command per machine here, as the user_id/wallet_id changes
            for i in started_instances_ready_for_command:
                ssm_command = await ssm_client.send_command(
                    [i.id],
                    command=create_deploy_cluster_stack_script(
                        app_settings,
                        cluster_machines_name_prefix=get_cluster_name(
                            app_settings,
                            user_id=user_id_from_instance_tags(i.tags),
                            wallet_id=wallet_id_from_instance_tags(i.tags),
                            is_manager=False,
                        ),
                        additional_custom_tags={
                            USER_ID_TAG_KEY: i.tags[USER_ID_TAG_KEY],
                            WALLET_ID_TAG_KEY: i.tags[WALLET_ID_TAG_KEY],
                            ROLE_TAG_KEY: WORKER_ROLE_TAG_VALUE,
                        },
                    ),
                    command_name=DOCKER_STACK_DEPLOY_COMMAND_NAME,
                )
            await ec2_client.set_instances_tags(
                started_instances_ready_for_command,
                tags={
                    DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY: AWSTagValue(
                        ssm_command.command_id
                    ),
                },
            )

    # the remaining instances are broken (they were at some point connected but now not anymore)
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
