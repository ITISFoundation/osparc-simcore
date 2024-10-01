# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import json
from pathlib import Path
from typing import Any, Iterable
from unittest.mock import AsyncMock, call
from uuid import UUID, uuid4

import pytest
from models_library.projects import NodesDict, ProjectID
from models_library.projects_networks import NetworksWithAliases
from models_library.projects_nodes import Node
from pydantic import BaseModel, PositiveInt
from pytest_mock.plugin import MockerFixture
from simcore_service_director_v2.modules.projects_networks import (
    _get_networks_with_aliases_for_default_network,
    _send_network_configuration_to_dynamic_sidecar,
)

# UTILS


class MockedCalls(BaseModel):
    detach: list[Any]
    attach: list[Any]


class Example(BaseModel):
    existing_networks_with_aliases: NetworksWithAliases
    new_networks_with_aliases: NetworksWithAliases
    expected_calls: MockedCalls

    @classmethod
    def using(
        cls,
        existing: dict[str, Any],
        new: dict[str, Any],
        detach: list[Any],
        attach: list[Any],
    ) -> "Example":
        return cls(
            existing_networks_with_aliases=NetworksWithAliases.model_validate(existing),
            new_networks_with_aliases=NetworksWithAliases.model_validate(new),
            expected_calls=MockedCalls(detach=detach, attach=attach),
        )


def _node_id(number: int) -> str:
    return f"{UUID(int=number)}"


def _node_alias(number: int) -> str:
    return f"node_alias_{number}"


def _network_name(number: int) -> str:
    return f"network_{number}"


@pytest.fixture
def examples_factory(mock_scheduler: AsyncMock, project_id: ProjectID) -> list[Example]:
    return [
        # nothing exists
        Example.using(
            existing={},
            new={
                _network_name(1): {
                    _node_id(1): _node_alias(1),
                    _node_id(2): _node_alias(2),
                }
            },
            detach=[],
            attach=[
                call.attach_project_network(
                    node_id=UUID(_node_id(2)),
                    project_network=_network_name(1),
                    network_alias=_node_alias(2),
                ),
                call.attach_project_network(
                    node_id=UUID(_node_id(1)),
                    project_network=_network_name(1),
                    network_alias=_node_alias(1),
                ),
            ],
        ),
        # with existing network, remove node 2
        Example.using(
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
                call.detach_project_network(
                    node_id=UUID(_node_id(2)),
                    project_network=_network_name(1),
                ),
            ],
            attach=[],
        ),
        # remove node 2 and add node 2 with different alias
        Example.using(
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
                call.detach_project_network(
                    node_id=UUID(_node_id(2)),
                    project_network=_network_name(1),
                ),
            ],
            attach=[
                call.attach_project_network(
                    node_id=UUID(_node_id(2)),
                    project_network=_network_name(1),
                    network_alias=_node_alias(3),
                ),
            ],
        ),
        # nothing happens when updates with the same content
        Example.using(
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
def dy_workbench_with_networkable_labels(mocks_dir: Path) -> NodesDict:
    dy_workbench_template = mocks_dir / "fake_dy_workbench_template.json"
    assert dy_workbench_template.exists()

    dy_workbench = json.loads(dy_workbench_template.read_text())

    parsed_workbench: NodesDict = {}

    for node_uuid, node_data in dy_workbench.items():
        node_data["label"] = f"label_{uuid4()}"
        parsed_workbench[node_uuid] = Node.model_validate(node_data)

    return parsed_workbench


@pytest.fixture
def fake_project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
def mock_docker_calls(mocker: MockerFixture) -> Iterable[dict[str, AsyncMock]]:
    requires_dynamic_sidecar_mock = AsyncMock()
    requires_dynamic_sidecar_mock.return_value = True
    class_base = "simcore_service_director_v2.modules.dynamic_sidecar.scheduler._task.DynamicSidecarsScheduler"
    mocked_items = {
        "attach": mocker.patch(f"{class_base}.attach_project_network", AsyncMock()),
        "detach": mocker.patch(f"{class_base}.detach_project_network", AsyncMock()),
        "requires_dynamic_sidecar": mocker.patch(
            "simcore_service_director_v2.modules.projects_networks.requires_dynamic_sidecar",
            requires_dynamic_sidecar_mock,
        ),
    }

    yield mocked_items


async def test_send_network_configuration_to_dynamic_sidecar(
    mock_scheduler: AsyncMock,
    project_id: ProjectID,
    examples_factory: list[Example],
    mock_docker_calls: dict[str, AsyncMock],
) -> None:
    for example in examples_factory:
        await _send_network_configuration_to_dynamic_sidecar(
            scheduler=mock_scheduler,
            project_id=project_id,
            new_networks_with_aliases=example.new_networks_with_aliases,
            existing_networks_with_aliases=example.existing_networks_with_aliases,
        )

        mock_scheduler.assert_has_calls(example.expected_calls.attach, any_order=True)
        mock_scheduler.assert_has_calls(example.expected_calls.detach, any_order=True)


async def test_get_networks_with_aliases_for_default_network_is_json_serializable(
    mock_director_v0_client: AsyncMock,
    fake_project_id: ProjectID,
    dy_workbench_with_networkable_labels: dict[str, Any],
    user_id: PositiveInt,
    rabbitmq_client: AsyncMock,
    mock_docker_calls: dict[str, AsyncMock],
) -> None:
    assert await _get_networks_with_aliases_for_default_network(
        project_id=fake_project_id,
        user_id=user_id,
        new_workbench=dy_workbench_with_networkable_labels,
        director_v0_client=mock_director_v0_client,
        rabbitmq_client=rabbitmq_client,
    )
