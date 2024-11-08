import asyncio
import logging
from datetime import UTC, datetime
from decimal import Decimal

from models_library.api_schemas_resource_usage_tracker.credit_transactions import (
    WalletTotalCredits,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.rabbitmq_messages import (
    CreditsLimit,
    WalletCreditsLimitReachedMessage,
    WalletCreditsMessage,
)
from models_library.resource_tracker import ServiceRunId, ServiceRunStatus
from models_library.users import UserID
from models_library.wallets import WalletID
from pydantic import PositiveInt
from servicelib.rabbitmq import RabbitMQClient

from .modules.db.repositories.resource_tracker import ResourceTrackerRepository

_logger = logging.getLogger(__name__)


def make_negative(n):
    return -abs(n)


async def sum_credit_transactions_and_publish_to_rabbitmq(
    resource_tracker_repo: ResourceTrackerRepository,
    rabbitmq_client: RabbitMQClient,
    product_name: ProductName,
    wallet_id: WalletID,
) -> WalletTotalCredits:
    wallet_total_credits = (
        await resource_tracker_repo.sum_credit_transactions_by_product_and_wallet(
            product_name,
            wallet_id,
        )
    )
    publish_message = WalletCreditsMessage.model_construct(
        wallet_id=wallet_id,
        created_at=datetime.now(tz=UTC),
        credits=wallet_total_credits.available_osparc_credits,
        product_name=product_name,
    )
    await rabbitmq_client.publish(publish_message.channel_name, publish_message)
    return wallet_total_credits


_BATCH_SIZE = 20


async def _publish_to_rabbitmq_wallet_credits_limit_reached(
    rabbitmq_client: RabbitMQClient,
    service_run_id: ServiceRunId,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    wallet_id: WalletID,
    credits_: Decimal,
    credits_limit: CreditsLimit,
):
    publish_message = WalletCreditsLimitReachedMessage(
        service_run_id=service_run_id,
        user_id=user_id,
        project_id=project_id,
        node_id=node_id,
        wallet_id=wallet_id,
        credits=credits_,
        credits_limit=credits_limit,
    )
    await rabbitmq_client.publish(publish_message.channel_name, publish_message)


async def publish_to_rabbitmq_wallet_credits_limit_reached(
    resource_tracker_repo: ResourceTrackerRepository,
    rabbitmq_client: RabbitMQClient,
    product_name: ProductName,
    wallet_id: WalletID,
    credits_: Decimal,
    credits_limit: CreditsLimit,
):
    # Get all current running services for that wallet
    total_count: PositiveInt = (
        await resource_tracker_repo.total_service_runs_by_product_and_user_and_wallet(
            product_name,
            user_id=None,
            wallet_id=wallet_id,
            service_run_status=ServiceRunStatus.RUNNING,
        )
    )

    for offset in range(0, total_count, _BATCH_SIZE):
        batch_services = await resource_tracker_repo.list_service_runs_by_product_and_user_and_wallet(
            product_name,
            user_id=None,
            wallet_id=wallet_id,
            offset=offset,
            limit=_BATCH_SIZE,
            service_run_status=ServiceRunStatus.RUNNING,
        )

        await asyncio.gather(
            *(
                _publish_to_rabbitmq_wallet_credits_limit_reached(
                    rabbitmq_client=rabbitmq_client,
                    service_run_id=service.service_run_id,
                    user_id=service.user_id,
                    project_id=service.project_id,
                    node_id=service.node_id,
                    wallet_id=wallet_id,
                    credits_=credits_,
                    credits_limit=credits_limit,
                )
                for service in batch_services
            )
        )


async def compute_service_run_credit_costs(
    start: datetime, stop: datetime, cost_per_unit: Decimal
) -> Decimal:
    if start <= stop:
        time_delta = stop - start
        return round(Decimal(time_delta.total_seconds() / 3600) * cost_per_unit, 2)
    msg = f"Stop {stop} is smaller then {start} this should not happen. Investigate."
    raise ValueError(msg)
