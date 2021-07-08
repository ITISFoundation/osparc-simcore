# pylint: disable=redefined-outer-name

import pytest
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
    SchedulerData,
    ServiceBootType,
    ServiceLabelsStoredData,
    ServiceState,
)


@pytest.fixture
def service_message() -> str:
    return "starting..."


@pytest.fixture
def service_state() -> ServiceState:
    return ServiceState.RUNNING


@pytest.mark.parametrize(
    "scheduler_data",
    [
        # pylint: disable=no-member
        pytest.lazy_fixture("scheduler_data_from_http_request"),
        pytest.lazy_fixture("scheduler_data_from_service_labels_stored_data"),
    ],
)
def test_running_service_details_make_status(
    scheduler_data: SchedulerData, service_message: str, service_state: ServiceState
):
    running_service_details = RunningDynamicServiceDetails.from_scheduler_data(
        node_uuid=scheduler_data.node_uuid,
        scheduler_data=scheduler_data,
        service_state=service_state,
        service_message=service_message,
    )
    print(running_service_details)
    assert running_service_details

    running_service_details_dict = running_service_details.dict(
        exclude_unset=True, by_alias=True
    )

    expected_running_service_details = {
        "boot_type": ServiceBootType.V2,
        "project_id": scheduler_data.project_id,
        "service_state": service_state,
        "service_message": service_message,
        "service_uuid": scheduler_data.node_uuid,
        "service_key": scheduler_data.key,
        "service_version": scheduler_data.version,
        "service_host": scheduler_data.service_name,
        "user_id": scheduler_data.user_id,
        "service_port": scheduler_data.service_port,
    }

    assert running_service_details_dict == expected_running_service_details


def test_service_labels_stored_data() -> None:
    sample = ServiceLabelsStoredData.Config.schema_extra["example"]
    assert ServiceLabelsStoredData(**sample)
