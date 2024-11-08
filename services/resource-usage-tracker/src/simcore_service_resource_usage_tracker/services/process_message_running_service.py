import logging
from collections.abc import Awaitable, Callable
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
from pydantic import TypeAdapter

from ..models.credit_transactions import (
    CreditTransactionCreate,
    CreditTransactionCreditsAndStatusUpdate,
    CreditTransactionCreditsUpdate,
)
from ..models.service_runs import (
    ServiceRunCreate,
    ServiceRunLastHeartbeatUpdate,
    ServiceRunStoppedAtUpdate,
)
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository
from .modules.rabbitmq import RabbitMQClient, get_rabbitmq_client
from .utils import (
    compute_service_run_credit_costs,
    make_negative,
    publish_to_rabbitmq_wallet_credits_limit_reached,
    sum_credit_transactions_and_publish_to_rabbitmq,
)

_logger = logging.getLogger(__name__)


async def process_message(app: FastAPI, data: bytes) -> bool:
    rabbit_message: RabbitResourceTrackingMessages = TypeAdapter(
        RabbitResourceTrackingMessages
    ).validate_json(data)
    _logger.info(
        "Process %s msg service_run_id: %s",
        rabbit_message.message_type,
        rabbit_message.service_run_id,
    )
    resource_tracker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=app.state.engine
    )
    rabbitmq_client = get_rabbitmq_client(app)

    await RABBIT_MSG_TYPE_TO_PROCESS_HANDLER[rabbit_message.message_type](
        resource_tracker_repo, rabbit_message, rabbitmq_client
    )
    return True


async def _process_start_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStartedMessage,
    rabbitmq_client: RabbitMQClient,
):
    service_run_db = await resource_tracker_repo.get_service_run_by_id(
        service_run_id=msg.service_run_id
    )
    if service_run_db:
        # NOTE: After we find out why sometimes RUT recieves multiple start events and fix it, we can change it to log level `error`
        _logger.warning(
            "On process start event the service run id %s already exists in DB, INVESTIGATE! Current msg created_at: %s, already stored msg created_at: %s",
            msg.service_run_id,
            msg.created_at,
            service_run_db.started_at,
        )
        return

    # Prepare `service run` record (if billable `credit transaction`) in the DB
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
        parent_project_id=msg.parent_project_id,
        root_parent_project_id=msg.root_parent_project_id,
        root_parent_project_name=msg.root_parent_project_name,
        parent_node_id=msg.parent_node_id,
        root_parent_node_id=msg.root_parent_node_id,
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
    service_run_db = await resource_tracker_repo.get_service_run_by_id(
        service_run_id=msg.service_run_id
    )
    if not service_run_db:
        _logger.error(
            "Recieved process heartbeat event for service_run_id: %s, but we do not have the started record in the DB, INVESTIGATE!",
            msg.service_run_id,
        )
        return
    if service_run_db.service_run_status in {
        ServiceRunStatus.SUCCESS,
        ServiceRunStatus.ERROR,
    }:
        _logger.error(
            "Recieved process heartbeat event for service_run_id: %s, but it was already closed, INVESTIGATE!",
            msg.service_run_id,
        )
        return

    # Update `service run` record (if billable `credit transaction`) in the DB
    update_service_run_last_heartbeat = ServiceRunLastHeartbeatUpdate(
        service_run_id=msg.service_run_id, last_heartbeat_at=msg.created_at
    )
    running_service = await resource_tracker_repo.update_service_run_last_heartbeat(
        update_service_run_last_heartbeat
    )
    if running_service is None:
        _logger.info("Nothing to update: %s", msg)
        return

    if running_service.wallet_id and running_service.pricing_unit_cost is not None:
        # Compute currently used credits
        computed_credits = await compute_service_run_credit_costs(
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
        if wallet_total_credits.available_osparc_credits < CreditsLimit.OUT_OF_CREDITS:
            await publish_to_rabbitmq_wallet_credits_limit_reached(
                resource_tracker_repo,
                rabbitmq_client,
                product_name=running_service.product_name,
                wallet_id=running_service.wallet_id,
                credits_=wallet_total_credits.available_osparc_credits,
                credits_limit=CreditsLimit.OUT_OF_CREDITS,
            )


async def _process_stop_event(
    resource_tracker_repo: ResourceTrackerRepository,
    msg: RabbitResourceTrackingStoppedMessage,
    rabbitmq_client: RabbitMQClient,
):
    service_run_db = await resource_tracker_repo.get_service_run_by_id(
        service_run_id=msg.service_run_id
    )
    if not service_run_db:
        # NOTE: ANE/MD discussed. When the RUT receives a stop event and has not received before any start or heartbeat event, it probably means that
        # we failed to start container. https://github.com/ITISFoundation/osparc-simcore/issues/5169
        _logger.warning(
            "Recieved stop event for service_run_id: %s, but we do not have any record in the DB, therefore the service probably didn't start correctly.",
            msg.service_run_id,
        )
        return
    if service_run_db.service_run_status in {
        ServiceRunStatus.SUCCESS,
        ServiceRunStatus.ERROR,
    }:
        _logger.error(
            "Recieved stop event for service_run_id: %s, but it was already closed, INVESTIGATE!",
            msg.service_run_id,
        )
        return

    # Update `service run` record (if billable `credit transaction`) in the DB
    _run_status, _run_status_msg = ServiceRunStatus.SUCCESS, None
    if msg.simcore_platform_status is SimcorePlatformStatus.BAD:
        _run_status, _run_status_msg = (
            ServiceRunStatus.ERROR,
            "Director-v2 or Sidecar considers service as unhealthy",
        )
    update_service_run_stopped_at = ServiceRunStoppedAtUpdate(
        service_run_id=msg.service_run_id,
        stopped_at=msg.created_at,
        service_run_status=_run_status,
        service_run_status_msg=_run_status_msg,
    )

    running_service = await resource_tracker_repo.update_service_run_stopped_at(
        update_service_run_stopped_at
    )

    if running_service is None:
        _logger.error("Nothing to update. This should not happen investigate.")
        return

    if running_service.wallet_id and running_service.pricing_unit_cost is not None:
        # Compute currently used credits
        computed_credits = await compute_service_run_credit_costs(
            running_service.started_at,
            msg.created_at,
            running_service.pricing_unit_cost,
        )
        # Update credits in the transaction table and close the transaction
        update_credit_transaction = CreditTransactionCreditsAndStatusUpdate(
            service_run_id=msg.service_run_id,
            osparc_credits=make_negative(computed_credits),
            transaction_status=(
                CreditTransactionStatus.BILLED
                if msg.simcore_platform_status == SimcorePlatformStatus.OK
                else CreditTransactionStatus.NOT_BILLED
            ),
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


RABBIT_MSG_TYPE_TO_PROCESS_HANDLER: dict[str, Callable[..., Awaitable[None]]] = {
    RabbitResourceTrackingMessageType.TRACKING_STARTED: _process_start_event,
    RabbitResourceTrackingMessageType.TRACKING_HEARTBEAT: _process_heartbeat_event,
    RabbitResourceTrackingMessageType.TRACKING_STOPPED: _process_stop_event,
}
