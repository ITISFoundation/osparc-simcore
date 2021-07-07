# pylint: disable=redefined-outer-name

import pytest
from simcore_service_director_v2.models.schemas.dynamic_services import (
    MonitorData,
    RunningDynamicServiceDetails,
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
    "monitor_data",
    [
        # pylint: disable=no-member
        pytest.lazy_fixture("monitor_data_from_http_request"),
        pytest.lazy_fixture("monitor_data_from_service_labels_stored_data"),
    ],
)
def test_running_service_details_make_status(
    monitor_data: MonitorData, service_message: str, service_state: ServiceState
):
    running_service_details = RunningDynamicServiceDetails.from_monitoring_status(
        node_uuid=monitor_data.node_uuid,
        monitor_data=monitor_data,
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
        "project_id": monitor_data.project_id,
        "service_state": service_state,
        "service_message": service_message,
        "service_uuid": monitor_data.node_uuid,
        "service_key": monitor_data.key,
        "service_version": monitor_data.version,
        "service_host": monitor_data.service_name,
        "user_id": monitor_data.user_id,
        "service_port": monitor_data.service_port,
    }

    assert running_service_details_dict == expected_running_service_details


def test_service_labels_stored_data() -> None:
    sample = ServiceLabelsStoredData.Config.schema_extra["example"]
    assert ServiceLabelsStoredData(**sample)
