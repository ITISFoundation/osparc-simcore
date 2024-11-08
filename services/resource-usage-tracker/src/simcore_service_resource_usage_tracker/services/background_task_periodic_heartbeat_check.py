import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from models_library.resource_tracker import (
    CreditTransactionStatus,
    ResourceTrackerServiceType,
    ServiceRunId,
    ServiceRunStatus,
)
from pydantic import NonNegativeInt, PositiveInt

from ..core.settings import ApplicationSettings
from ..models.credit_transactions import CreditTransactionCreditsAndStatusUpdate
from ..models.service_runs import ServiceRunStoppedAtUpdate
from .modules.db.repositories.resource_tracker import ResourceTrackerRepository
from .utils import compute_service_run_credit_costs, make_negative

_logger = logging.getLogger(__name__)

_BATCH_SIZE = 20


async def _check_service_heartbeat(
    resource_tracker_repo: ResourceTrackerRepository,
    base_start_timestamp: datetime,
    resource_usage_tracker_missed_heartbeat_interval: timedelta,
    resource_usage_tracker_missed_heartbeat_counter_fail: NonNegativeInt,
    service_run_id: ServiceRunId,
    last_heartbeat_at: datetime,
    missed_heartbeat_counter: NonNegativeInt,
    modified_at: datetime,
):
    # Check for missed heartbeats
    if (
        # Checks that in last 5 minutes we didn't get any heartbeat (ex. last heartbeat < current time - 5 minutes).
        last_heartbeat_at
        < base_start_timestamp - resource_usage_tracker_missed_heartbeat_interval
    ) and (  # Checks that last modified timestamp is older than some reasonable small threshold (this is here to prevent situation
        # when RUT is restarting and in the beginning starts the `check_of_running_services_task`. If the task was already running in
        # last 2 minutes it will not allow it to compute. )
        modified_at
        < base_start_timestamp - timedelta(minutes=2)
    ):
        missed_heartbeat_counter += 1
        if (
            missed_heartbeat_counter
            > resource_usage_tracker_missed_heartbeat_counter_fail
        ):
            # Handle unhealthy service
            _logger.error(
                "Service run id: %s is considered unhealthy and not billed. Counter %s",
                service_run_id,
                missed_heartbeat_counter,
            )
            await _close_unhealthy_service(
                resource_tracker_repo, service_run_id, base_start_timestamp
            )
        else:
            _logger.warning(
                "Service run id: %s missed heartbeat. Counter %s",
                service_run_id,
                missed_heartbeat_counter,
            )
            await resource_tracker_repo.update_service_missed_heartbeat_counter(
                service_run_id, last_heartbeat_at, missed_heartbeat_counter
            )


async def _close_unhealthy_service(
    resource_tracker_repo: ResourceTrackerRepository,
    service_run_id: ServiceRunId,
    base_start_timestamp: datetime,
):
    # 1. Close the service_run
    update_service_run_stopped_at = ServiceRunStoppedAtUpdate(
        service_run_id=service_run_id,
        stopped_at=base_start_timestamp,
        service_run_status=ServiceRunStatus.ERROR,
        service_run_status_msg="Service missed more heartbeats. It's considered unhealthy.",
    )
    running_service = await resource_tracker_repo.update_service_run_stopped_at(
        update_service_run_stopped_at
    )

    if running_service is None:
        _logger.error(
            "Service run id: %s Nothing to update. This should not happen; investigate.",
            service_run_id,
        )
        return

    # 2. Close the billing transaction (as not billed)
    if running_service.wallet_id and running_service.pricing_unit_cost is not None:
        computed_credits = await compute_service_run_credit_costs(
            running_service.started_at,
            running_service.last_heartbeat_at,
            running_service.pricing_unit_cost,
        )
        update_credit_transaction = CreditTransactionCreditsAndStatusUpdate(
            service_run_id=service_run_id,
            osparc_credits=make_negative(computed_credits),
            transaction_status=(
                CreditTransactionStatus.NOT_BILLED
                if running_service.service_type
                == ResourceTrackerServiceType.COMPUTATIONAL_SERVICE
                else CreditTransactionStatus.BILLED
            ),
        )
        await resource_tracker_repo.update_credit_transaction_credits_and_status(
            update_credit_transaction
        )


async def periodic_check_of_running_services_task(app: FastAPI) -> None:
    _logger.info("Periodic check started")

    # This check runs across all products
    app_settings: ApplicationSettings = app.state.settings
    resource_tracker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=app.state.engine
    )

    base_start_timestamp = datetime.now(tz=timezone.utc)

    # Get all current running services (across all products)
    total_count: PositiveInt = (
        await resource_tracker_repo.total_service_runs_with_running_status_across_all_products()
    )

    for offset in range(0, total_count, _BATCH_SIZE):
        batch_check_services = await resource_tracker_repo.list_service_runs_with_running_status_across_all_products(
            offset=offset,
            limit=_BATCH_SIZE,
        )

        await asyncio.gather(
            *(
                _check_service_heartbeat(
                    resource_tracker_repo=resource_tracker_repo,
                    base_start_timestamp=base_start_timestamp,
                    resource_usage_tracker_missed_heartbeat_interval=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_INTERVAL_SEC,
                    resource_usage_tracker_missed_heartbeat_counter_fail=app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_COUNTER_FAIL,
                    service_run_id=check_service.service_run_id,
                    last_heartbeat_at=check_service.last_heartbeat_at,
                    missed_heartbeat_counter=check_service.missed_heartbeat_counter,
                    modified_at=check_service.modified,
                )
                for check_service in batch_check_services
            )
        )
