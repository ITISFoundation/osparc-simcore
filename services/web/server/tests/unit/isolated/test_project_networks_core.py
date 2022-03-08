# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from importlib import reload
from typing import Any, Dict, Iterable, List
from unittest.mock import AsyncMock, call
from uuid import UUID, uuid4

import pytest
import simcore_service_webserver
from models_library.projects import ProjectID
from models_library.project_networks import NetworksWithAliases
from pydantic import BaseModel
from pytest_mock.plugin import MockerFixture
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.project_networks_core import (
    _get_networks_with_aliases_for_default_network,
    _send_network_configuration_to_dynamic_sidecar,
)

# UTILS


class MockedCalls(BaseModel):
    detach: List[Any]
    attach: List[Any]


class TestCase(BaseModel):
    existing_networks_with_aliases: NetworksWithAliases
    new_networks_with_aliases: NetworksWithAliases
    expected_calls: MockedCalls

    @classmethod
    def using(
        cls,
        existing: Dict[str, Any],
        new: Dict[str, Any],
        detach: List[Any],
        attach: List[Any],
    ) -> "TestCase":
        return cls(
            existing_networks_with_aliases=NetworksWithAliases.parse_obj(existing),
            new_networks_with_aliases=NetworksWithAliases.parse_obj(new),
            expected_calls=MockedCalls(detach=detach, attach=attach),
        )


def _node_id(number: int) -> str:
    return f"{UUID(int=number)}"


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
            existing={},
            new={
                _network_name(1): {
                    _node_id(1): _node_alias(1),
                    _node_id(2): _node_alias(2),
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
            existing={
                _network_name(1): {
                    _node_id(1): _node_alias(1),
                    _node_id(2): _node_alias(2),
                }
            },
            new={
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
            existing={
                _network_name(1): {
                    _node_id(1): _node_alias(1),
                    _node_id(2): _node_alias(2),
                }
            },
            new={
                _network_name(1): {
                    _node_id(1): _node_alias(1),
                    _node_id(2): _node_alias(3),
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
            existing={
                _network_name(1): {
                    _node_id(1): _node_alias(1),
                    _node_id(2): _node_alias(2),
                }
            },
            new={
                _network_name(1): {
                    _node_id(1): _node_alias(1),
                    _node_id(2): _node_alias(2),
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
def fake_workbench_with_networkable_labels(fake_project: ProjectDict) -> Dict[str, Any]:
    for node_data in fake_project["workbench"].values():
        node_data["label"] = f"label_{uuid4()}"
    return fake_project["workbench"]


@pytest.fixture
def fake_project_id(fake_project: ProjectDict) -> ProjectID:
    return UUID(fake_project["uuid"])


@pytest.fixture
def mock_requires_dynamic_sidecar(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_webserver.director_v2_api.requires_dynamic_sidecar",
        return_value=True,
    )


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
            new_networks_with_aliases=test_case.new_networks_with_aliases,
            existing_networks_with_aliases=test_case.existing_networks_with_aliases,
        )

        mock_director_v2_api["attach"].assert_has_awaits(
            test_case.expected_calls.attach, any_order=True
        )

        mock_director_v2_api["detach"].assert_has_awaits(
            test_case.expected_calls.detach, any_order=True
        )


async def test_get_networks_with_aliases_for_default_network_is_json_serializable(
    mock_app: AsyncMock,
    fake_project_id: ProjectID,
    fake_workbench_with_networkable_labels: Dict[str, Any],
    mock_requires_dynamic_sidecar: None,
) -> None:
    assert await _get_networks_with_aliases_for_default_network(
        mock_app,
        project_id=fake_project_id,
        new_workbench=fake_workbench_with_networkable_labels,
    )
