# pylint: disable=redefined-outer-name
import uuid

import pytest
from models_library.service_settings_labels import SimcoreServiceLabels
from simcore_service_director_v2.models.domains.dynamic_services import (
    DynamicServiceCreate,
)
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
    ServiceBootType,
    ServiceDetails,
    ServiceState,
)
from simcore_service_director_v2.modules.dynamic_sidecar.monitor import (
    MonitorData,
    ServiceLabelsStoredData,
)


@pytest.fixture
def port() -> int:
    return 1222


@pytest.fixture
def service_message() -> str:
    return "starting..."


@pytest.fixture
def service_state() -> ServiceState:
    return ServiceState.RUNNING


@pytest.fixture
def simcore_service_labels() -> SimcoreServiceLabels:
    return SimcoreServiceLabels(
        **SimcoreServiceLabels.Config.schema_extra["examples"][1]
    )


@pytest.fixture
def dynamic_service_create() -> DynamicServiceCreate:
    return DynamicServiceCreate.parse_obj(ServiceDetails.Config.schema_extra["example"])


@pytest.fixture
def service_labels_stored_data() -> ServiceLabelsStoredData:
    return ServiceLabelsStoredData.parse_obj(
        ServiceLabelsStoredData.Config.schema_extra["example"]
    )


@pytest.fixture
def from_http_request(
    dynamic_service_create: DynamicServiceCreate,
    simcore_service_labels: SimcoreServiceLabels,
    port: int,
) -> MonitorData:
    return MonitorData.make_from_http_request(
        service_name="some service",
        service=dynamic_service_create,
        simcore_service_labels=simcore_service_labels,
        dynamic_sidecar_network_name="some_network_name",
        simcore_traefik_zone="main",
        hostname="some host",
        port=port,
    )


@pytest.fixture
def from_service_labels_stored_data(
    service_labels_stored_data: ServiceLabelsStoredData, port: int
) -> MonitorData:
    return MonitorData.make_from_service_labels_stored_data(
        service_labels_stored_data=service_labels_stored_data, port=port
    )


@pytest.mark.parametrize(
    "monitor_data",
    [
        # pylint: disable=no-member
        pytest.lazy_fixture("from_http_request"),
        pytest.lazy_fixture("from_service_labels_stored_data"),
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
        "project_id": uuid.UUID(monitor_data.project_id),
        "service_state": service_state,
        "service_message": service_message,
        "service_uuid": monitor_data.node_uuid,
        "service_key": monitor_data.service_key,
        "service_version": monitor_data.service_tag,
        "service_host": monitor_data.service_name,
        "user_id": monitor_data.user_id,
        "service_port": monitor_data.service_port,
    }

    assert running_service_details_dict == expected_running_service_details
