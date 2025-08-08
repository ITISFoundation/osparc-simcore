import asyncio
import logging
from datetime import UTC, datetime, timedelta

from fastapi import FastAPI
from models_library.resource_tracker import (
    CreditTransactionStatus,
    ResourceTrackerServiceType,
    ServiceRunStatus,
)
from models_library.services_types import ServiceRunID
from pydantic import NonNegativeInt, PositiveInt
from sqlalchemy.ext.asyncio import AsyncEngine

from ..core.settings import ApplicationSettings
from ..models.credit_transactions import CreditTransactionCreditsAndStatusUpdate
from ..models.service_runs import ServiceRunStoppedAtUpdate
from .modules.db import (
    credit_transactions_db,
    licensed_items_checkouts_db,
    service_runs_db,
)
from .utils import compute_service_run_credit_costs, make_negative

_logger = logging.getLogger(__name__)

_BATCH_SIZE = 20


async def _check_service_heartbeat(
    db_engine: AsyncEngine,
    base_start_timestamp: datetime,
    resource_usage_tracker_missed_heartbeat_interval: timedelta,
    resource_usage_tracker_missed_heartbeat_counter_fail: NonNegativeInt,
    service_run_id: ServiceRunID,
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
                db_engine, service_run_id, base_start_timestamp
            )
        else:
            _logger.warning(
                "Service run id: %s missed heartbeat. Counter %s",
                service_run_id,
                missed_heartbeat_counter,
            )
            await service_runs_db.update_service_missed_heartbeat_counter(
                db_engine,
                service_run_id=service_run_id,
                last_heartbeat_at=last_heartbeat_at,
                missed_heartbeat_counter=missed_heartbeat_counter,
            )


async def _close_unhealthy_service(
    db_engine: AsyncEngine,
    service_run_id: ServiceRunID,
    base_start_timestamp: datetime,
):

    # 1. Close the service_run
    update_service_run_stopped_at = ServiceRunStoppedAtUpdate(
        service_run_id=service_run_id,
        stopped_at=base_start_timestamp,
        service_run_status=ServiceRunStatus.ERROR,
        service_run_status_msg="Service missed more heartbeats. It's considered unhealthy.",
    )
    running_service = await service_runs_db.update_service_run_stopped_at(
        db_engine, data=update_service_run_stopped_at
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
        # NOTE: I have decided that in the case of an error on our side, we will
        # close the Dynamic service as BILLED -> since the user was effectively using it until
        # the issue occurred.
        # NOTE: Update Jan 2025 - With the introduction of the IN_DEBT state,
        # when closing the transaction for the dynamic service as BILLED, it is possible
        # that the wallet may show a negative balance during this period, which would typically
        # be considered as IN_DEBT. However, I have decided to still close it as BILLED.
        # This ensures that the user does not have to explicitly pay the DEBT, as the closure
        # was caused by an issue on our side.
        _transaction_status = (
            CreditTransactionStatus.NOT_BILLED
            if running_service.service_type
            == ResourceTrackerServiceType.COMPUTATIONAL_SERVICE
            else CreditTransactionStatus.BILLED
        )
        update_credit_transaction = CreditTransactionCreditsAndStatusUpdate(
            service_run_id=service_run_id,
            osparc_credits=make_negative(computed_credits),
            transaction_status=_transaction_status,
        )
        await credit_transactions_db.update_credit_transaction_credits_and_status(
            db_engine, data=update_credit_transaction
        )

        # 3. If the credit transaction status is considered "NOT_BILLED", this might return
        # the wallet to positive numbers. If, in the meantime, some transactions were marked as DEBT,
        # we need to update them back to the BILLED state.
        if _transaction_status == CreditTransactionStatus.NOT_BILLED:
            wallet_total_credits = await credit_transactions_db.sum_wallet_credits(
                db_engine,
                product_name=running_service.product_name,
                wallet_id=running_service.wallet_id,
            )
            if wallet_total_credits.available_osparc_credits >= 0:
                await credit_transactions_db.batch_update_credit_transaction_status_for_in_debt_transactions(
                    db_engine,
                    project_id=None,
                    wallet_id=running_service.wallet_id,
                    transaction_status=CreditTransactionStatus.BILLED,
                )

    # 4. Release license seats in case some were checked out but not properly released.
    await licensed_items_checkouts_db.force_release_license_seats_by_run_id(
        db_engine, service_run_id=service_run_id
    )


async def check_running_services(app: FastAPI) -> None:
    _logger.info("Periodic check started")

    # This check runs across all products
    app_settings: ApplicationSettings = app.state.settings
    _db_engine = app.state.engine

    base_start_timestamp = datetime.now(tz=UTC)

    # Get all current running services (across all products)
    total_count: PositiveInt = (
        await service_runs_db.total_service_runs_with_running_status_across_all_products(
            _db_engine
        )
    )

    for offset in range(0, total_count, _BATCH_SIZE):
        batch_check_services = await service_runs_db.list_service_runs_with_running_status_across_all_products(
            _db_engine,
            offset=offset,
            limit=_BATCH_SIZE,
        )

        await asyncio.gather(
            *(
                _check_service_heartbeat(
                    db_engine=_db_engine,
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
