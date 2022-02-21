# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from importlib import reload
from typing import Any, Dict, Iterable, List
from unittest.mock import AsyncMock, call
from uuid import UUID, uuid4

import pytest
import simcore_service_webserver
from models_library.projects import ProjectID
from models_library.sharing_networks import SharingNetworks
from pydantic import BaseModel
from pytest_mock.plugin import MockerFixture
from simcore_service_webserver.sharing_networks import (
    _get_sharing_networks_for_default_network,
    _send_network_configuration_to_dynamic_sidecar,
)

# UTILS


class MockedCalls(BaseModel):
    detach: List[Any]
    attach: List[Any]


class TestCase(BaseModel):
    existing_sharing_networks: SharingNetworks
    new_sharing_networks: SharingNetworks
    expected_calls: MockedCalls

    @classmethod
    def using(
        cls,
        existing_sharing_networks: Dict[str, Any],
        new_sharing_networks: Dict[str, Any],
        detach: List[Any],
        attach: List[Any],
    ) -> "TestCase":
        return cls(
            existing_sharing_networks=SharingNetworks.parse_obj(
                existing_sharing_networks
            ),
            new_sharing_networks=SharingNetworks.parse_obj(new_sharing_networks),
            expected_calls=MockedCalls(detach=detach, attach=attach),
        )


def _node_id(number: int) -> UUID:
    return UUID(int=number)


def _node_alias(number: int) -> str:
    return f"node_alias_{number}"


def _network_name(number: int) -> str:
    return f"network_{number}"


# FIXTURES


@pytest.fixture
def test_case_factory(mock_app: AsyncMock, project_id: ProjectID) -> List[TestCase]:
    return [
        # nothing exists
        TestCase.using(
            existing_sharing_networks={},
            new_sharing_networks={
                _network_name(1): {
                    f"{_node_id(1)}": _node_alias(1),
                    f"{_node_id(2)}": _node_alias(2),
                }
            },
            detach=[],
            attach=[
                call(
                    app=mock_app,
                    project_id=project_id,
                    node_id=_node_id(2),
                    network_name=_network_name(1),
                    network_alias=_node_alias(2),
                ),
                call(
                    app=mock_app,
                    project_id=project_id,
                    node_id=_node_id(1),
                    network_name=_network_name(1),
                    network_alias=_node_alias(1),
                ),
            ],
        ),
        # with existing network, remove node 2
        TestCase.using(
            existing_sharing_networks={
                _network_name(1): {
                    f"{_node_id(1)}": _node_alias(1),
                    f"{_node_id(2)}": _node_alias(2),
                }
            },
            new_sharing_networks={
                _network_name(1): {
                    f"{_node_id(1)}": _node_alias(1),
                }
            },
            detach=[
                call(
                    app=mock_app,
                    project_id=project_id,
                    node_id=_node_id(2),
                    network_name=_network_name(1),
                ),
            ],
            attach=[],
        ),
        # remove node 2 and add node 2 with different alias
        TestCase.using(
            existing_sharing_networks={
                _network_name(1): {
                    f"{_node_id(1)}": _node_alias(1),
                    f"{_node_id(2)}": _node_alias(2),
                }
            },
            new_sharing_networks={
                _network_name(1): {
                    f"{_node_id(1)}": _node_alias(1),
                    f"{_node_id(2)}": _node_alias(3),
                }
            },
            detach=[
                call(
                    app=mock_app,
                    project_id=project_id,
                    node_id=_node_id(2),
                    network_name=_network_name(1),
                ),
            ],
            attach=[
                call(
                    app=mock_app,
                    project_id=project_id,
                    node_id=_node_id(2),
                    network_name=_network_name(1),
                    network_alias=_node_alias(3),
                ),
            ],
        ),
        # nothing happens when updates with the same content
        TestCase.using(
            existing_sharing_networks={
                _network_name(1): {
                    f"{_node_id(1)}": _node_alias(1),
                    f"{_node_id(2)}": _node_alias(2),
                }
            },
            new_sharing_networks={
                _network_name(1): {
                    f"{_node_id(1)}": _node_alias(1),
                    f"{_node_id(2)}": _node_alias(2),
                }
            },
            detach=[],
            attach=[],
        ),
    ]


@pytest.fixture
def mock_app() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def mock_director_v2_api(mocker: MockerFixture) -> Iterable[Dict[str, AsyncMock]]:
    requires_dynamic_sidecar_mock = AsyncMock()
    requires_dynamic_sidecar_mock.return_value = True
    mocked_items = {
        "attach": mocker.patch(
            "simcore_service_webserver.director_v2_core.attach_network_to_dynamic_sidecar",
            AsyncMock(),
        ),
        "detach": mocker.patch(
            "simcore_service_webserver.director_v2_core.detach_network_from_dynamic_sidecar",
            AsyncMock(),
        ),
        "requires_dynamic_sidecar": mocker.patch(
            "simcore_service_webserver.director_v2_core.requires_dynamic_sidecar",
            requires_dynamic_sidecar_mock,
        ),
    }

    reload(simcore_service_webserver.director_v2_api)

    yield mocked_items


@pytest.fixture
def project_with_networkable_labels(
    fake_project_data: Dict[str, Any],
) -> Dict[str, Any]:
    for node_data in fake_project_data["workbench"].values():
        node_data["label"] = f"label_{uuid4()}"
    return fake_project_data


# TESTS


async def test_send_network_configuration_to_dynamic_sidecar(
    mock_app: AsyncMock,
    project_id: ProjectID,
    mock_director_v2_api: Dict[str, AsyncMock],
    test_case_factory: List[TestCase],
) -> None:
    for test_case in test_case_factory:

        await _send_network_configuration_to_dynamic_sidecar(
            app=mock_app,
            project_id=project_id,
            new_sharing_networks=test_case.new_sharing_networks,
            sharing_networks=test_case.existing_sharing_networks,
        )

        mock_director_v2_api["attach"].assert_has_awaits(
            test_case.expected_calls.attach, any_order=True
        )

        mock_director_v2_api["detach"].assert_has_awaits(
            test_case.expected_calls.detach, any_order=True
        )


async def test_get_sharing_networks_for_default_network_is_json_serializable(
    mock_app: AsyncMock, project_with_networkable_labels: Dict[str, Any]
) -> None:
    assert await _get_sharing_networks_for_default_network(
        mock_app, new_project_data=project_with_networkable_labels
    )
