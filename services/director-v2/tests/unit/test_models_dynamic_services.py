# pylint: disable=redefined-outer-name

from typing import Dict, Set

import pytest
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
    SchedulerData,
    ServiceBootType,
    ServiceLabelsStoredData,
    ServiceState,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_states import (
    extract_containers_minimim_statuses,
)

# FIXTURES


@pytest.fixture
def service_message() -> str:
    return "starting..."


@pytest.fixture
def service_state() -> ServiceState:
    return ServiceState.RUNNING


@pytest.fixture
def mock_containers_statuses() -> Dict[str, Dict[str, str]]:
    return {
        "container_id_1": {"Status": "created"},
        "container_id_2": {"Status": "dead", "Error": "something"},
        "container_id_3": {"Status": "running"},
    }


# UTILS

# the following is the predefined expected ordering, change below test only if
# this order is not adequate anymore
_EXPECTED_ORDER = [
    ServiceState.FAILED,
    ServiceState.PENDING,
    ServiceState.PULLING,
    ServiceState.STARTING,
    ServiceState.RUNNING,
    ServiceState.COMPLETE,
]


def _all_states() -> Set[ServiceState]:
    return set(x for x in ServiceState)


# TESTS


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


def test_all_states_are_mapped():
    service_state_defined: Set[ServiceState] = _all_states()
    comparison_mapped: Set[ServiceState] = set(ServiceState.comparison_order().keys())
    assert (
        service_state_defined == comparison_mapped
    ), "entries from _COMPARISON_ORDER do not match all states in ServiceState"


def test_equality():
    for service_state in _all_states():
        assert service_state == ServiceState(service_state.value)


def test_expected_order():
    for k, service_state in enumerate(_EXPECTED_ORDER):
        prior_states = _EXPECTED_ORDER[:k]
        for prior_service_state in prior_states:
            assert prior_service_state < service_state
            assert prior_service_state != service_state
            assert service_state > prior_service_state


def test_min_service_state_is_lowerst_in_expected_order():
    for i in range(len(_EXPECTED_ORDER)):
        items_after_index = _EXPECTED_ORDER[i:]
        assert min(items_after_index) == items_after_index[0]


def test_extract_containers_minimim_statuses(
    mock_containers_statuses: Dict[str, Dict[str, str]]
):
    service_state, service_message = extract_containers_minimim_statuses(
        mock_containers_statuses
    )
    assert service_state == ServiceState.FAILED
    assert service_message == "something"
