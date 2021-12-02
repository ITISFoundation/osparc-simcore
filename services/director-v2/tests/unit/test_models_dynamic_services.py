# pylint: disable=redefined-outer-name
import random
import string
from collections import namedtuple
from typing import Dict, List, Set

import pytest
from simcore_service_director_v2.models.schemas.dynamic_services import (
    RunningDynamicServiceDetails,
    SchedulerData,
    ServiceBootType,
    ServiceLabelsStoredData,
    ServiceState,
)
from simcore_service_director_v2.modules.dynamic_sidecar.docker_states import (
    CONTAINER_STATUSES_FAILED,
    extract_containers_minimim_statuses,
)

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

CNT_STS_RESTARTING = "restarting"
CNT_STS_DEAD = "dead"
CNT_STS_PAUSED = "paused"
CNT_STS_CREATED = "created"
CNT_STS_RUNNING = "running"
CNT_STS_REMOVING = "removing"
CNT_STS_EXITED = "exited"

ALL_CONTAINER_STATUSES: Set[str] = {
    CNT_STS_RESTARTING,
    CNT_STS_DEAD,
    CNT_STS_PAUSED,
    CNT_STS_CREATED,
    CNT_STS_RUNNING,
    CNT_STS_REMOVING,
    CNT_STS_EXITED,
}

RANDOM_STRING_DATASET = string.ascii_letters + string.digits

ExpectedStatus = namedtuple("ExpectedStatus", "containers_statuses, expected_state")

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


def _random_string(length: int = 4) -> str:
    return "".join(random.choices(RANDOM_STRING_DATASET, k=length))


def _make_status_dict(status: str) -> Dict[str, str]:
    assert status in ALL_CONTAINER_STATUSES
    status_dict = {"Status": status}
    if status in CONTAINER_STATUSES_FAILED:
        status_dict["Error"] = "failed state here"
    return status_dict


def containers_statues(*args: str) -> Dict[str, Dict[str, str]]:
    return {_random_string(): _make_status_dict(x) for x in args}


def _all_states() -> Set[ServiceState]:
    return set(x for x in ServiceState)


SAMPLE_EXPECTED_STATUSES: List[ExpectedStatus] = [
    ExpectedStatus(
        containers_statuses=containers_statues(
            CNT_STS_RESTARTING, CNT_STS_RUNNING, CNT_STS_EXITED
        ),
        expected_state=ServiceState.FAILED,
    ),
    ExpectedStatus(
        containers_statuses=containers_statues(
            CNT_STS_CREATED, CNT_STS_RUNNING, CNT_STS_EXITED
        ),
        expected_state=ServiceState.STARTING,
    ),
    ExpectedStatus(
        containers_statuses=containers_statues(CNT_STS_RUNNING, CNT_STS_EXITED),
        expected_state=ServiceState.RUNNING,
    ),
    ExpectedStatus(
        containers_statuses=containers_statues(CNT_STS_REMOVING, CNT_STS_EXITED),
        expected_state=ServiceState.COMPLETE,
    ),
]

# TESTS
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


@pytest.mark.parametrize(
    "containers_statuses, expected_state",
    [(x.containers_statuses, x.expected_state) for x in SAMPLE_EXPECTED_STATUSES],
    ids=[x.expected_state.name for x in SAMPLE_EXPECTED_STATUSES],
)
def test_extract_containers_minimim_statuses(
    containers_statuses: Dict[str, Dict[str, str]], expected_state: ServiceState
):
    service_state, _ = extract_containers_minimim_statuses(containers_statuses)
    assert service_state == expected_state


def test_not_implemented_comparison() -> None:
    with pytest.raises(TypeError):
        # pylint: disable=pointless-statement
        ServiceState.FAILED > {}  # type: ignore


def test_regression_legacy_service_compatibility() -> None:
    api_response = {
        "published_port": None,
        "entry_point": "",
        "service_uuid": "e5aa2f7a-eac4-4522-bd4f-270b5d8d9fff",
        "service_key": "simcore/services/dynamic/mocked",
        "service_version": "1.6.10",
        "service_host": "mocked_e5aa2f7a-eac4-4522-bd4f-270b5d8d9fff",
        "service_port": 8888,
        "service_basepath": "/x/e5aa2f7a-eac4-4522-bd4f-270b5d8d9fff",
        "service_state": "running",
        "service_message": "",
        "user_id": "1",
        "project_id": "b1ec5c8e-f5bb-11eb-b1d5-02420a000006",
    }
    service_details = RunningDynamicServiceDetails.parse_obj(api_response)

    assert service_details

    service_url = f"http://{service_details.host}:{service_details.internal_port}{service_details.basepath}"
    assert service_url == service_details.legacy_service_url
