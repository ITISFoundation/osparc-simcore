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


def _log_instance(instance: EC2InstanceData) -> str:
    """Consistent instance identifier for log messages with enough info
    to locate the instance in AWS and in our logging facilities."""
    user_id = instance.tags.get("user_id", "N/A")
    wallet_id = instance.tags.get("wallet_id", "N/A")
    return f"[id={instance.id} dns={instance.aws_private_dns} user_id={user_id} wallet_id={wallet_id}]"


def _get_instance_last_heartbeat(instance: EC2InstanceData) -> datetime.datetime | None:
    if last_heartbeat := instance.tags.get(
        HEARTBEAT_TAG_KEY,
    ):
        last_heartbeat_time: datetime.datetime = arrow.get(last_heartbeat).datetime
        return last_heartbeat_time

    return None


_USER_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("user_id")
_WALLET_ID_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("wallet_id")


async def _get_all_associated_worker_instances(
    app: FastAPI,
    primary_instances: Iterable[EC2InstanceData],
) -> set[EC2InstanceData]:
    worker_instances: set[EC2InstanceData] = set()
    for instance in primary_instances:
        assert "user_id" in instance.tags  # nosec
        user_id = TypeAdapter(UserID).validate_python(instance.tags[_USER_ID_TAG_KEY])
        assert "wallet_id" in instance.tags  # nosec
        # NOTE: wallet_id can be None
        wallet_id = (
            TypeAdapter(WalletID).validate_python(instance.tags[_WALLET_ID_TAG_KEY])
            if instance.tags[_WALLET_ID_TAG_KEY] != "None"
            else None
        )

        worker_instances.update(await get_cluster_workers(app, user_id=user_id, wallet_id=wallet_id))
    return worker_instances


async def _find_terminateable_instances(app: FastAPI, instances: Iterable[EC2InstanceData]) -> set[EC2InstanceData]:
    app_settings = get_application_settings(app)
    assert app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES  # nosec

    # get the corresponding ec2 instance data
    terminateable_instances: set[EC2InstanceData] = set()

    time_to_wait_before_termination = (
        app_settings.CLUSTERS_KEEPER_MAX_MISSED_HEARTBEATS_BEFORE_CLUSTER_TERMINATION
        * app_settings.SERVICE_TRACKING_HEARTBEAT
    )
    startup_delay = app_settings.CLUSTERS_KEEPER_PRIMARY_EC2_INSTANCES.PRIMARY_EC2_INSTANCES_MAX_START_TIME
    for instance in instances:
        if last_heartbeat := _get_instance_last_heartbeat(instance):
            elapsed_time_since_heartbeat = arrow.utcnow().datetime - last_heartbeat
            allowed_time_to_wait = time_to_wait_before_termination
            if elapsed_time_since_heartbeat >= allowed_time_to_wait:
                terminateable_instances.add(instance)
            else:
                _logger.info(
                    "%s has still %ss before being terminateable",
                    _log_instance(instance),
                    f"{(allowed_time_to_wait - elapsed_time_since_heartbeat).total_seconds():.0f}",
                )
        else:
            elapsed_time_since_startup = arrow.utcnow().datetime - instance.launch_time
            allowed_time_to_wait = startup_delay
            if elapsed_time_since_startup >= allowed_time_to_wait:
                terminateable_instances.add(instance)

    # get all terminateable instances associated worker instances
    worker_instances = await _get_all_associated_worker_instances(app, terminateable_instances)

    return terminateable_instances.union(worker_instances)


async def _heartbeat_connected_clusters(app: FastAPI, connected_instances: set[EC2InstanceData]) -> None:
    """Update heartbeat for all connected clusters. Log busy ones."""
    for instance in connected_instances:
        with log_catch(_logger, reraise=False):
            # NOTE: a connected instance could break between these 2 calls;
            # silenced and handled next cycle
            if await is_scheduler_busy(get_scheduler_url(instance), get_scheduler_auth(app)):
                _logger.info("%s is running tasks", _log_instance(instance))
                await set_instance_heartbeat(app, instance=instance)


async def _terminate_idle_clusters(app: FastAPI, connected_instances: set[EC2InstanceData]) -> None:
    if terminateable_instances := await _find_terminateable_instances(app, connected_instances):
        await delete_clusters(app, instances=terminateable_instances)


async def _handle_starting_clusters(app: FastAPI, starting_instances: set[EC2InstanceData]) -> None:
    if not starting_instances:
        return

    _logger.info(
        "Found %d starting instances (no heartbeat, awaiting deployment): %s",
        len(starting_instances),
        [_log_instance(i) for i in starting_instances],
    )

    # terminate instances that have been starting for too long
    if terminateable_instances := await _find_terminateable_instances(app, starting_instances):
        for instance in terminateable_instances:
            elapsed = arrow.utcnow().datetime - instance.launch_time
            _logger.warning(
                "Stalled startup, will terminate (started but never connected): %s elapsed=%ss",
                _log_instance(instance),
                f"{elapsed.total_seconds():.0f}",
            )
        await delete_clusters(app, instances=terminateable_instances)

    # deploy docker stack to instances that still need it
    instances_in_need_of_deployment = {
        i for i in starting_instances - terminateable_instances if DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY not in i.tags
    }
    if instances_in_need_of_deployment:
        await _deploy_to_instances(app, instances_in_need_of_deployment)


async def _deploy_to_instances(app: FastAPI, instances: set[EC2InstanceData]) -> None:
    ssm_client = get_ssm_client(app)
    ssm_connection_states = await limited_gather(
        *[ssm_client.is_instance_connected_to_ssm_server(i.id) for i in instances],
        reraise=False,
        log=_logger,
        limit=20,
    )
    ssm_ready = [i for i, c in zip(instances, ssm_connection_states, strict=True) if c is True]
    ssm_not_ready = [i for i, c in zip(instances, ssm_connection_states, strict=True) if c is not True]
    if ssm_not_ready:
        _logger.info(
            "SSM not ready for %d instances (will retry next check): %s",
            len(ssm_not_ready),
            [_log_instance(i) for i in ssm_not_ready],
        )

    app_settings = get_application_settings(app)
    ec2_client = get_ec2_client(app)
    # Each instance is handled independently so a failure on one does not block the others
    for instance in ssm_ready:
        with log_catch(_logger, reraise=False):
            ssm_command = await ssm_client.send_command(
                [instance.id],
                command=create_deploy_cluster_stack_script(
                    app_settings,
                    cluster_machines_name_prefix=get_cluster_name(
                        app_settings,
                        user_id=user_id_from_instance_tags(instance.tags),
                        wallet_id=wallet_id_from_instance_tags(instance.tags),
                        is_manager=False,
                    ),
                    additional_custom_tags={
                        USER_ID_TAG_KEY: instance.tags[USER_ID_TAG_KEY],
                        WALLET_ID_TAG_KEY: instance.tags[WALLET_ID_TAG_KEY],
                        ROLE_TAG_KEY: WORKER_ROLE_TAG_VALUE,
                    },
                ),
                command_name=DOCKER_STACK_DEPLOY_COMMAND_NAME,
            )
            _logger.info(
                "Deployment command sent: %s command_id=%s",
                _log_instance(instance),
                ssm_command.command_id,
            )
            await ec2_client.set_instances_tags(
                [instance],
                tags={
                    DOCKER_STACK_DEPLOY_COMMAND_EC2_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
                        ssm_command.command_id
                    ),
                },
            )


async def _handle_broken_clusters(app: FastAPI, broken_instances: set[EC2InstanceData]) -> None:
    if not broken_instances:
        return

    _logger.warning(
        "Found %d broken instances (were connected but now disconnected): %s",
        len(broken_instances),
        [_log_instance(i) for i in broken_instances],
    )
    if terminateable_instances := await _find_terminateable_instances(app, broken_instances):
        for instance in terminateable_instances:
            elapsed = arrow.utcnow().datetime - instance.launch_time
            _logger.error(
                "Terminating unresponsive instance: %s uptime=%ss"
                " (TIP: was connected but became unresponsive, please check instance logs)",
                _log_instance(instance),
                f"{elapsed.total_seconds():.0f}",
            )
        await delete_clusters(app, instances=terminateable_instances)


async def check_clusters(app: FastAPI) -> None:
    primary_instances = await get_all_clusters(app)
    connected = {i for i in primary_instances if await ping_scheduler(get_scheduler_url(i), get_scheduler_auth(app))}
    disconnected = primary_instances - connected

    await _heartbeat_connected_clusters(app, connected)
    await _terminate_idle_clusters(app, connected)

    starting = {i for i in disconnected if _get_instance_last_heartbeat(i) is None}
    await _handle_starting_clusters(app, starting)

    broken = disconnected - starting
    await _handle_broken_clusters(app, broken)
