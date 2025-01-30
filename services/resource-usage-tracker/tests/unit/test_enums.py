# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name


from models_library import resource_tracker
from simcore_postgres_database.models.resource_tracker_credit_transactions import (
    CreditTransactionClassification,
    CreditTransactionStatus,
)
from simcore_postgres_database.models.resource_tracker_service_runs import (
    ResourceTrackerServiceRunStatus,
)


def test_postgres_and_models_library_enums_are_in_sync():
    assert list(resource_tracker.CreditTransactionStatus) == list(
        CreditTransactionStatus
    )
    assert list(resource_tracker.CreditClassification) == list(
        CreditTransactionClassification
    )
    assert list(resource_tracker.ServiceRunStatus) == list(
        ResourceTrackerServiceRunStatus
    )
