import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.rabbitmq_messages import (
    CreditsLimit,
    RabbitResourceTrackingHeartbeatMessage,
    RabbitResourceTrackingMessages,
    RabbitResourceTrackingMessageType,
    RabbitResourceTrackingStartedMessage,
    RabbitResourceTrackingStoppedMessage,
    SimcorePlatformStatus,
)
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionStatus,
    ResourceTrackerServiceType,
    ServiceRunStatus,
)
from models_library.services import ServiceType
from pydantic import parse_raw_as

from .models.resource_tracker_credit_transactions import (
    CreditTransactionCreate,
    CreditTransactionCreditsAndStatusUpdate,
    CreditTransactionCreditsUpdate,
)
from .models.resource_tracker_service_runs import (
    ServiceRunCreate,
    ServiceRunLastHeartbeatUpdate,
    ServiceRunStoppedAtUpdate,
)
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository
from .modules.rabbitmq import RabbitMQClient, get_rabbitmq_client
from .resource_tracker_utils import (
    make_negative,
    publish_to_rabbitmq_wallet_credits_limit_reached,
    sum_credit_transactions_and_publish_to_rabbitmq,
)

_logger = logging.getLogger(__name__)


async def process_message(app: FastAPI, data: bytes) -> bool:
    rabbit_message = parse_raw_as(RabbitResourceTrackingMessages, data)
    _logger.info("Process msg service_run_id: %s", rabbit_message.service_run_id)
    resource_tacker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=app.state.engine
    )
    rabbitmq_client = get_rabbitmq_client(app)

    await RABBIT_MSG_TYPE_TO_PROCESS_HANDLER[rabbit_message.message_type](
        resource_tacker_repo, rabbit_message, rabbitmq_client
    )
    return True


async def _process_start_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStartedMessage,
    rabbitmq_client: RabbitMQClient,
):
    service_type = (
        ResourceTrackerServiceType.COMPUTATIONAL_SERVICE
        if msg.service_type == ServiceType.COMPUTATIONAL
        else ResourceTrackerServiceType.DYNAMIC_SERVICE
    )

    pricing_unit_cost = None
    if msg.pricing_unit_cost_id:
        pricing_unit_cost_db = await resource_tracker_repo.get_pricing_unit_cost_by_id(
            pricing_unit_cost_id=msg.pricing_unit_cost_id
        )
        pricing_unit_cost = pricing_unit_cost_db.cost_per_unit

    create_service_run = ServiceRunCreate(
        product_name=msg.product_name,
        service_run_id=msg.service_run_id,
        wallet_id=msg.wallet_id,
        wallet_name=msg.wallet_name,
        pricing_plan_id=msg.pricing_plan_id,
        pricing_unit_id=msg.pricing_unit_id,
        pricing_unit_cost_id=msg.pricing_unit_cost_id,
        pricing_unit_cost=pricing_unit_cost,
        simcore_user_agent=msg.simcore_user_agent,
        user_id=msg.user_id,
        user_email=msg.user_email,
        project_id=msg.project_id,
        project_name=msg.project_name,
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
    service_run_id = await resource_tracker_repo.create_service_run(create_service_run)

    if msg.wallet_id and msg.wallet_name:
        transaction_create = CreditTransactionCreate(
            product_name=msg.product_name,
            wallet_id=msg.wallet_id,
            wallet_name=msg.wallet_name,
            pricing_plan_id=msg.pricing_plan_id,
            pricing_unit_id=msg.pricing_unit_id,
            pricing_unit_cost_id=msg.pricing_unit_cost_id,
            user_id=msg.user_id,
            user_email=msg.user_email,
            osparc_credits=Decimal(0.0),
            transaction_status=CreditTransactionStatus.PENDING,
            transaction_classification=CreditClassification.DEDUCT_SERVICE_RUN,
            service_run_id=service_run_id,
            payment_transaction_id=None,
            created_at=msg.created_at,
            last_heartbeat_at=msg.created_at,
        )
        await resource_tracker_repo.create_credit_transaction(transaction_create)

        # Publish wallet total credits to RabbitMQ
        await sum_credit_transactions_and_publish_to_rabbitmq(
            resource_tracker_repo, rabbitmq_client, msg.product_name, msg.wallet_id
        )


async def _process_heartbeat_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingHeartbeatMessage,
    rabbitmq_client: RabbitMQClient,
):
    update_service_run_last_heartbeat = ServiceRunLastHeartbeatUpdate(
        service_run_id=msg.service_run_id, last_heartbeat_at=msg.created_at
    )

    running_service = await resource_tracker_repo.update_service_run_last_heartbeat(
        update_service_run_last_heartbeat
    )
    if running_service is None:
        _logger.info("Nothing to update: %s", msg)
        return

    if running_service.wallet_id and running_service.pricing_unit_cost:
        # Compute currently used credits
        computed_credits = await _compute_service_run_credit_costs(
            running_service.started_at,
            msg.created_at,
            running_service.pricing_unit_cost,
        )
        # Update credits in the transaction table
        update_credit_transaction = CreditTransactionCreditsUpdate(
            service_run_id=msg.service_run_id,
            osparc_credits=make_negative(computed_credits),
            last_heartbeat_at=msg.created_at,
        )
        await resource_tracker_repo.update_credit_transaction_credits(
            update_credit_transaction
        )
        # Publish wallet total credits to RabbitMQ
        wallet_total_credits = await sum_credit_transactions_and_publish_to_rabbitmq(
            resource_tracker_repo,
            rabbitmq_client,
            running_service.product_name,
            running_service.wallet_id,
        )
        if wallet_total_credits.available_osparc_credits < CreditsLimit.MIN_CREDITS:
            await publish_to_rabbitmq_wallet_credits_limit_reached(
                resource_tracker_repo,
                rabbitmq_client,
                product_name=running_service.product_name,
                wallet_id=running_service.wallet_id,
                credits_=wallet_total_credits.available_osparc_credits,
                credits_limit=CreditsLimit.MIN_CREDITS,
            )


async def _process_stop_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStoppedMessage,
    rabbitmq_client: RabbitMQClient,
):
    update_service_run_stopped_at = ServiceRunStoppedAtUpdate(
        service_run_id=msg.service_run_id,
        stopped_at=msg.created_at,
        service_run_status=ServiceRunStatus.SUCCESS
        if msg.simcore_platform_status == SimcorePlatformStatus.OK
        else ServiceRunStatus.ERROR,
    )

    running_service = await resource_tracker_repo.update_service_run_stopped_at(
        update_service_run_stopped_at
    )

    if running_service is None:
        _logger.error("Nothing to update. This should not happen investigate.")
        return

    if running_service.wallet_id and running_service.pricing_unit_cost:
        # Compute currently used credits
        computed_credits = await _compute_service_run_credit_costs(
            running_service.started_at,
            msg.created_at,
            running_service.pricing_unit_cost,
        )
        # Update credits in the transaction table and close the transaction
        update_credit_transaction = CreditTransactionCreditsAndStatusUpdate(
            service_run_id=msg.service_run_id,
            osparc_credits=-computed_credits,  # negative(computed_credits)
            transaction_status=CreditTransactionStatus.BILLED
            if msg.simcore_platform_status == SimcorePlatformStatus.OK
            else CreditTransactionStatus.NOT_BILLED,
        )
        await resource_tracker_repo.update_credit_transaction_credits_and_status(
            update_credit_transaction
        )
        # Publish wallet total credits to RabbitMQ
        await sum_credit_transactions_and_publish_to_rabbitmq(
            resource_tracker_repo,
            rabbitmq_client,
            running_service.product_name,
            running_service.wallet_id,
        )


RABBIT_MSG_TYPE_TO_PROCESS_HANDLER: dict[str, Callable[..., Awaitable[None]],] = {
    RabbitResourceTrackingMessageType.TRACKING_STARTED: _process_start_event,
    RabbitResourceTrackingMessageType.TRACKING_HEARTBEAT: _process_heartbeat_event,
    RabbitResourceTrackingMessageType.TRACKING_STOPPED: _process_stop_event,
}


async def _compute_service_run_credit_costs(
    start: datetime, stop: datetime, cost_per_unit: Decimal
) -> Decimal:
    if start <= stop:
        time_delta = stop - start
        return round(Decimal(time_delta.seconds / 3600) * cost_per_unit, 2)
    msg = f"Stop {stop} is smaller then {start} this should not happen. Investigate."
    raise ValueError(msg)
