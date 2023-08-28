import logging
from typing import cast

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.rabbitmq_messages import (
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingMessages,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.resource_tracker import ResourceTrackerServiceType, ServiceRunStatus
from pydantic import parse_raw_as

from .models.resource_tracker_service_run import (
    ServiceRunCreate,
    ServiceRunLastHeartbeatUpdate,
    ServiceRunStoppedAtUpdate,
)
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository

_logger = logging.getLogger(__name__)


async def process_message(
    app: FastAPI, data: bytes  # pylint: disable=unused-argument
) -> bool:
    rabbit_message = parse_raw_as(RabbitResourceTrackingMessages, data)
    rabbit_message_type = type(rabbit_message)

    resource_tacker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=app.state.engine
    )

    if rabbit_message_type == RabbitResourceTrackingStartedMessage:
        await _process_start_event(
            resource_tacker_repo,
            cast(RabbitResourceTrackingStartedMessage, rabbit_message),
        )
    elif rabbit_message_type == RabbitResourceTrackingHeartbeatMessage:
        await _process_heartbeat_event(
            resource_tacker_repo,
            cast(RabbitResourceTrackingHeartbeatMessage, rabbit_message),
        )
    elif rabbit_message_type == RabbitResourceTrackingStoppedMessage:
        await _process_stop_event(
            resource_tacker_repo,
            cast(RabbitResourceTrackingStoppedMessage, rabbit_message),
        )
    else:
        raise NotImplementedError

    _logger.debug("%s", data)
    return True


async def _process_start_event(
    resource_tacker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStartedMessage,
):
    service_type = (
        ResourceTrackerServiceType.COMPUTATIONAL_SERVICE
        if msg.service_type == "COMPUTATIONAL"
        else ResourceTrackerServiceType.DYNAMIC_SERVICE
    )

    create_service_run = ServiceRunCreate(
        product_name=msg.product_name,
        service_run_id=msg.service_run_id,
        wallet_id=msg.wallet_id,
        wallet_name=msg.wallet_name,
        pricing_plan_id=None,
        pricing_detail_id=None,
        simcore_user_agent=msg.simcore_user_agent,
        user_id=msg.user_id,
        user_email=msg.user_email,
        project_id=msg.project_id,
        project_name=msg.product_name,
        node_id=msg.node_id,
        node_name=msg.node_name,
        service_key=msg.service_key,
        service_version=msg.service_version,
        service_type=service_type,
        service_resources=jsonable_encoder(msg.service_resources),
        service_additional_metadata={},
        started_at=msg.created_at,
        service_run_status=ServiceRunStatus.RUNNING,
        last_heartbeat_at=msg.created_at,
    )
    await resource_tacker_repo.create_service_run(create_service_run)


async def _process_heartbeat_event(
    resource_tacker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingHeartbeatMessage,
):
    update_service_run_last_heartbeat = ServiceRunLastHeartbeatUpdate(
        service_run_id=msg.service_run_id, last_heartbeat_at=msg.created_at
    )

    await resource_tacker_repo.update_service_run_last_heartbeat(
        update_service_run_last_heartbeat
    )


async def _process_stop_event(
    resource_tacker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStoppedMessage,
):
    update_service_run_stopped_at = ServiceRunStoppedAtUpdate(
        service_run_id=msg.service_run_id,
        stopped_at=msg.created_at,
        service_run_status=ServiceRunStatus.SUCCESS
        if msg.simcore_platform_status == SimcorePlatformStatus.OK
        else ServiceRunStatus.ERROR,
    )

    await resource_tacker_repo.update_service_run_stopped_at(
        update_service_run_stopped_at
    )
