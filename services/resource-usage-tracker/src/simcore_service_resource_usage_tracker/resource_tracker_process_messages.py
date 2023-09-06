import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from decimal import Decimal

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.rabbitmq_messages import (
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
from pydantic import parse_raw_as

from .models.resource_tracker_credit_transactions import (
    CreditTransactionCreate,
    CreditTransactionCreditsAndStatusUpdate,
    CreditTransactionCreditsUpdate,
)
from .models.resource_tracker_service_run import (
    ServiceRunCreate,
    ServiceRunLastHeartbeatUpdate,
    ServiceRunStoppedAtUpdate,
)
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository
from .resource_tracker_utils import make_negative

_logger = logging.getLogger(__name__)


async def process_message(
    app: FastAPI, data: bytes  # pylint: disable=unused-argument
) -> bool:
    rabbit_message = parse_raw_as(RabbitResourceTrackingMessages, data)

    resource_tacker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=app.state.engine
    )

    await RABBIT_MSG_TYPE_TO_PROCESS_HANDLER[rabbit_message.message_type](
        resource_tacker_repo, rabbit_message
    )

    _logger.debug("%s", data)
    return True


async def _process_start_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStartedMessage,
):
    service_type = (
        ResourceTrackerServiceType.COMPUTATIONAL_SERVICE
        if msg.service_type == "COMPUTATIONAL"
        else ResourceTrackerServiceType.DYNAMIC_SERVICE
    )

    pricing_detail_cost_per_unit = None
    if msg.pricing_detail_id:
        pricing_detail_cost_per_unit = (
            await resource_tracker_repo.get_pricing_detail_cost_per_unit(
                msg.pricing_detail_id
            )
        )

    create_service_run = ServiceRunCreate(
        product_name=msg.product_name,
        service_run_id=msg.service_run_id,
        wallet_id=msg.wallet_id,
        wallet_name=msg.wallet_name,
        pricing_plan_id=msg.pricing_plan_id,
        pricing_detail_id=msg.pricing_detail_id,
        pricing_detail_cost_per_unit=pricing_detail_cost_per_unit,
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
    service_run_id = await resource_tracker_repo.create_service_run(create_service_run)

    if msg.wallet_id and msg.wallet_name:
        transaction_create = CreditTransactionCreate(
            product_name=msg.product_name,
            wallet_id=msg.wallet_id,
            wallet_name=msg.wallet_name,
            pricing_plan_id=msg.pricing_plan_id,
            pricing_detail_id=msg.pricing_detail_id,
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


async def _process_heartbeat_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingHeartbeatMessage,
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

    if running_service.wallet_id and running_service.pricing_detail_cost_per_unit:
        # Compute currently used credits
        computed_credits = await _compute_service_run_credit_costs(
            running_service.started_at,
            msg.created_at,
            running_service.pricing_detail_cost_per_unit,
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

        wallet_total_credits = (
            await resource_tracker_repo.sum_credit_transactions_by_product_and_wallet(
                running_service.product_name,
                running_service.wallet_id,
            )
        )
        assert wallet_total_credits  # nosec
        # NOTE: Publish wallet total credits to RabbitMQ


async def _process_stop_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStoppedMessage,
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

    if running_service.wallet_id and running_service.pricing_detail_cost_per_unit:
        # Compute currently used credits
        computed_credits = await _compute_service_run_credit_costs(
            running_service.started_at,
            msg.created_at,
            running_service.pricing_detail_cost_per_unit,
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

        wallet_total_credits = (
            await resource_tracker_repo.sum_credit_transactions_by_product_and_wallet(
                running_service.product_name,
                running_service.wallet_id,
            )
        )
        assert wallet_total_credits  # nosec
        # NOTE: Publish wallet total credits to RabbitMQ


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
