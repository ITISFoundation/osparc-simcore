# pylint: disable=redefined-outer-name

from typing import Set, Dict

import pytest

from simcore_service_director_v2.modules.dynamic_sidecar.parse_docker_status import (
    ServiceState,
    _SERVICE_STATE_COMPARISON_ORDER,
    extract_containers_minimim_statuses,
)


@pytest.fixture
def mock_containers_statuses() -> Dict[str, Dict[str, str]]:
    return {
        "container_id_1": {"Status": "pulling"},
        "container_id_2": {"Status": "removing", "Error": "something"},
        "container_id_3": {"Status": "pending"},
    }


# the following is the predefined expected ordering, change below test only if
# this order is not adequate anymore
_EXPECTED_ORDER = [
    ServiceState.PENDING,
    ServiceState.PULLING,
    ServiceState.STARTING,
    ServiceState.RUNNING,
    ServiceState.COMPLETE,
    ServiceState.FAILED,
]


def _all_states() -> Set[ServiceState]:
    return set(x for x in ServiceState)


def test_all_states_are_mapped():
    service_state_defined: Set[ServiceState] = _all_states()
    comparison_mapped: Set[ServiceState] = set(_SERVICE_STATE_COMPARISON_ORDER.keys())
    assert (
        service_state_defined == comparison_mapped
    ), "entries from _SERVICE_STATE_COMPARISON_ORDER do not match all states in ServiceState"


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
    assert service_state == ServiceState.PENDING
    assert service_message == ""