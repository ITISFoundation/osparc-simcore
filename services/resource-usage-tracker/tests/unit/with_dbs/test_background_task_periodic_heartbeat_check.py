from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from models_library.resource_tracker import (
    CreditTransactionStatus,
    ResourceTrackerServiceType,
    ServiceRunStatus,
)
from servicelib.rabbitmq import RabbitMQClient
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    resource_tracker_credit_transactions,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    resource_tracker_service_runs,
)
from simcore_service_resource_usage_tracker.core.settings import ApplicationSettings
from simcore_service_resource_usage_tracker.models.credit_transactions import (
    CreditTransactionDB,
)
from simcore_service_resource_usage_tracker.models.service_runs import ServiceRunDB
from simcore_service_resource_usage_tracker.services.background_task_periodic_heartbeat_check import (
    periodic_check_of_running_services_task,
)
from simcore_service_resource_usage_tracker.services.modules.db.repositories.resource_tracker import (
    ResourceTrackerRepository,
)

pytest_simcore_core_services_selection = ["postgres", "rabbit"]
pytest_simcore_ops_services_selection = [
    "adminer",
]

_SERVICE_RUN_ID_OSPARC_10_MIN_OLD = "1"
_SERVICE_RUN_ID_S4L_10_MIN_OLD = "2"
_SERVICE_RUN_ID_OSPARC_NOW = "3"

_LAST_HEARTBEAT_10_MIN_OLD = datetime.now(tz=timezone.utc) - timedelta(minutes=10)
_LAST_HEARTBEAT_NOW = datetime.now(tz=timezone.utc)


@pytest.fixture()
def resource_tracker_setup_db(
    postgres_db: sa.engine.Engine,
    random_resource_tracker_service_run,
    random_resource_tracker_credit_transactions,
) -> Iterator[None]:
    with postgres_db.connect() as con:
        # Populate service runs table
        con.execute(
            resource_tracker_service_runs.insert().values(
                **random_resource_tracker_service_run(
                    service_run_id=_SERVICE_RUN_ID_OSPARC_10_MIN_OLD,
                    service_type=ResourceTrackerServiceType.COMPUTATIONAL_SERVICE,
                    product_name="osparc",
                    last_heartbeat_at=_LAST_HEARTBEAT_10_MIN_OLD,
                    modified=_LAST_HEARTBEAT_10_MIN_OLD,
                    started_at=_LAST_HEARTBEAT_10_MIN_OLD - timedelta(minutes=1),
                )
            )
        )
        con.execute(
            resource_tracker_service_runs.insert().values(
                **random_resource_tracker_service_run(
                    service_run_id=_SERVICE_RUN_ID_S4L_10_MIN_OLD,
                    service_type=ResourceTrackerServiceType.DYNAMIC_SERVICE,
                    product_name="s4l",
                    last_heartbeat_at=_LAST_HEARTBEAT_10_MIN_OLD,
                    modified=_LAST_HEARTBEAT_10_MIN_OLD,
                    started_at=_LAST_HEARTBEAT_10_MIN_OLD - timedelta(minutes=1),
                )
            )
        )
        con.execute(
            resource_tracker_service_runs.insert().values(
                **random_resource_tracker_service_run(
                    service_run_id=_SERVICE_RUN_ID_OSPARC_NOW,
                    product_name="osparc",
                    modified=_LAST_HEARTBEAT_NOW,
                    last_heartbeat_at=_LAST_HEARTBEAT_NOW,
                )
            )
        )
        # Populate credit transactions table
        con.execute(
            resource_tracker_credit_transactions.insert().values(
                **random_resource_tracker_credit_transactions(
                    service_run_id=_SERVICE_RUN_ID_OSPARC_10_MIN_OLD,
                    product_name="osparc",
                    modified=_LAST_HEARTBEAT_10_MIN_OLD,
                    last_heartbeat_at=_LAST_HEARTBEAT_10_MIN_OLD,
                    transaction_status="PENDING",
                )
            )
        )
        con.execute(
            resource_tracker_credit_transactions.insert().values(
                **random_resource_tracker_credit_transactions(
                    service_run_id=_SERVICE_RUN_ID_S4L_10_MIN_OLD,
                    product_name="s4l",
                    modified=_LAST_HEARTBEAT_10_MIN_OLD,
                    last_heartbeat_at=_LAST_HEARTBEAT_10_MIN_OLD,
                    transaction_status="PENDING",
                )
            )
        )
        con.execute(
            resource_tracker_credit_transactions.insert().values(
                **random_resource_tracker_credit_transactions(
                    service_run_id=_SERVICE_RUN_ID_OSPARC_NOW,
                    product_name="osparc",
                    modified=_LAST_HEARTBEAT_NOW,
                    last_heartbeat_at=_LAST_HEARTBEAT_NOW,
                    transaction_status="PENDING",
                )
            )
        )

        yield

        con.execute(resource_tracker_credit_transactions.delete())
        con.execute(resource_tracker_service_runs.delete())


async def test_process_event_functions(
    create_rabbitmq_client: Callable[[str], RabbitMQClient],
    mocked_redis_server: None,
    postgres_db: sa.engine.Engine,
    resource_tracker_setup_db,
    initialized_app,
):
    engine = initialized_app.state.engine
    app_settings: ApplicationSettings = initialized_app.state.settings
    resource_tracker_repo: ResourceTrackerRepository = ResourceTrackerRepository(
        db_engine=engine
    )

    for _ in range(app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_COUNTER_FAIL):
        await periodic_check_of_running_services_task(initialized_app)
        # NOTE: As we are doing check that the modified field needs to be older then some
        # threshold, we need to make this field artificaly older in this test
        with postgres_db.connect() as con:
            fake_old_modified_at = datetime.now(tz=timezone.utc) - timedelta(minutes=5)
            update_stmt = resource_tracker_service_runs.update().values(
                modified=fake_old_modified_at
            )
            con.execute(update_stmt)

    # Check max acceptable missed heartbeats reached before considering them as unhealthy
    with postgres_db.connect() as con:
        result = con.execute(sa.select(resource_tracker_service_runs))
        service_run_db = [ServiceRunDB.model_validate(row) for row in result]
    for service_run in service_run_db:
        if service_run.service_run_id in (
            _SERVICE_RUN_ID_OSPARC_10_MIN_OLD,
            _SERVICE_RUN_ID_S4L_10_MIN_OLD,
        ):
            assert (
                service_run.missed_heartbeat_counter
                == app_settings.RESOURCE_USAGE_TRACKER_MISSED_HEARTBEAT_COUNTER_FAIL
            )
            assert service_run.service_run_status == ServiceRunStatus.RUNNING
        else:
            assert service_run.missed_heartbeat_counter == 0
            assert service_run.service_run_status == ServiceRunStatus.RUNNING

    # Now we call the function one more time and it should consider some of running services as unhealthy
    await periodic_check_of_running_services_task(initialized_app)

    with postgres_db.connect() as con:
        result = con.execute(sa.select(resource_tracker_service_runs))
        service_run_db = [ServiceRunDB.model_validate(row) for row in result]
    for service_run in service_run_db:
        if service_run.service_run_id in (
            _SERVICE_RUN_ID_OSPARC_10_MIN_OLD,
            _SERVICE_RUN_ID_S4L_10_MIN_OLD,
        ):
            assert service_run.service_run_status == ServiceRunStatus.ERROR
            assert service_run.service_run_status_msg is not None
        else:
            assert service_run.missed_heartbeat_counter == 0
            assert service_run.service_run_status == ServiceRunStatus.RUNNING

    with postgres_db.connect() as con:
        result = con.execute(sa.select(resource_tracker_credit_transactions))
        credit_transaction_db = [
            CreditTransactionDB.model_validate(row) for row in result
        ]
    for transaction in credit_transaction_db:
        if transaction.service_run_id in (
            _SERVICE_RUN_ID_OSPARC_10_MIN_OLD,
            _SERVICE_RUN_ID_S4L_10_MIN_OLD,
        ):
            if transaction.service_run_id == _SERVICE_RUN_ID_OSPARC_10_MIN_OLD:
                # Computational service is not billed
                assert (
                    transaction.transaction_status == CreditTransactionStatus.NOT_BILLED
                )
            else:
                # Dynamic service is billed
                assert transaction.transaction_status == CreditTransactionStatus.BILLED
        else:
            assert transaction.transaction_status == CreditTransactionStatus.PENDING
