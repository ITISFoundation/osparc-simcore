# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List
from unittest.mock import AsyncMock, call
from uuid import UUID, uuid4

import pytest
from models_library.project_networks import NetworksWithAliases
from models_library.projects import ProjectID
from pydantic import BaseModel, PositiveInt
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.modules.project_networks import (
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
def test_case_factory(
    mock_scheduler: AsyncMock, project_id: ProjectID
) -> List[TestCase]:
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
                    scheduler=mock_scheduler,
                    project_id=project_id,
                    node_id=_node_id(2),
                    network_name=_network_name(1),
                    network_alias=_node_alias(2),
                ),
                call(
                    scheduler=mock_scheduler,
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
                    scheduler=mock_scheduler,
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
                    scheduler=mock_scheduler,
                    project_id=project_id,
                    node_id=_node_id(2),
                    network_name=_network_name(1),
                ),
            ],
            attach=[
                call(
                    scheduler=mock_scheduler,
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
def mock_scheduler() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_director_v0_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def rabbitmq_client() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def dy_workbench_with_networkable_labels(mocks_dir: Path) -> Dict[str, Any]:
    dy_workbench_template = mocks_dir / "fake_dy_workbench_template.json"
    assert dy_workbench_template.exists()

    dy_workbench = json.loads(dy_workbench_template.read_text())

    for node_data in dy_workbench.values():
        node_data["label"] = f"label_{uuid4()}"
    return dy_workbench


@pytest.fixture
def fake_project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def user_id() -> PositiveInt:
    return 1


@pytest.fixture
def mock_docker_calls(mocker: MockerFixture) -> Iterable[Dict[str, AsyncMock]]:
    requires_dynamic_sidecar_mock = AsyncMock()
    requires_dynamic_sidecar_mock.return_value = True
    mocked_items = {
        "attach": mocker.patch(
            "simcore_service_director_v2.modules.project_networks._attach_network_to_dynamic_sidecar",
            AsyncMock(),
        ),
        "detach": mocker.patch(
            "simcore_service_director_v2.modules.project_networks._detach_network_from_dynamic_sidecar",
            AsyncMock(),
        ),
        "requires_dynamic_sidecar": mocker.patch(
            "simcore_service_director_v2.modules.project_networks._requires_dynamic_sidecar",
            requires_dynamic_sidecar_mock,
        ),
    }

    # reload(simcore_service_webserver.director_v2_api)

    yield mocked_items


# TESTS


async def test_send_network_configuration_to_dynamic_sidecar(
    mock_scheduler: AsyncMock,
    project_id: ProjectID,
    test_case_factory: List[TestCase],
    mock_docker_calls: Dict[str, AsyncMock],
) -> None:
    for test_case in test_case_factory:

        await _send_network_configuration_to_dynamic_sidecar(
            scheduler=mock_scheduler,
            project_id=project_id,
            new_networks_with_aliases=test_case.new_networks_with_aliases,
            existing_networks_with_aliases=test_case.existing_networks_with_aliases,
        )

        mock_docker_calls["attach"].assert_has_awaits(
            test_case.expected_calls.attach, any_order=True
        )

        mock_docker_calls["detach"].assert_has_awaits(
            test_case.expected_calls.detach, any_order=True
        )


async def test_get_networks_with_aliases_for_default_network_is_json_serializable(
    mock_director_v0_client: AsyncMock,
    fake_project_id: ProjectID,
    dy_workbench_with_networkable_labels: Dict[str, Any],
    user_id: PositiveInt,
    rabbitmq_client: AsyncMock,
    mock_docker_calls: Dict[str, AsyncMock],
) -> None:
    assert await _get_networks_with_aliases_for_default_network(
        project_id=fake_project_id,
        user_id=user_id,
        new_workbench=dy_workbench_with_networkable_labels,
        director_v0_client=mock_director_v0_client,
        rabbitmq_client=rabbitmq_client,
    )
