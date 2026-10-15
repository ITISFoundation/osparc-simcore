# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
"""Deadlock between two node PATCH requests of the same project

Every write to `projects_nodes` updates the parent `projects` row through the
`projects_nodes_changed` trigger, i.e. it takes the node row first and the `projects` row last.
A graph mutation (`run_project_graph_mutation`) locks the `projects` row first. A node PATCH that
is not a graph mutation does not lock it at all, so the two take the same two locks in opposite
order when they patch the same node:

    graph PATCH:    lock projects row            -> UPDATE projects_nodes row N (waits for the other)
    non-graph PATCH:                UPDATE projects_nodes row N -> trigger UPDATE projects (waits)

PostgreSQL aborts one of them with SQLSTATE 40P01, i.e. the client gets a 500.
See https://github.com/ITISFoundation/private-issues/issues/669
"""

import asyncio
from typing import Any, Final
from unittest import mock

import pytest
import sqlalchemy as sa
from aiohttp import ClientResponse
from aiohttp.test_utils import TestClient
from models_library.projects import ProjectID
from pytest_mock import MockerFixture
from pytest_simcore.helpers.assert_checks import assert_status
from servicelib.aiohttp import status
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects import _projects_repository
from simcore_service_webserver.projects.models import ProjectDict
from sqlalchemy.ext.asyncio import AsyncConnection
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_delay, wait_fixed

_TIMEOUT_S: Final[float] = 30.0
_SOMEONE_WAITS_FOR_A_LOCK_SQL: Final[str] = "SELECT count(*) FROM pg_stat_activity WHERE wait_event_type = 'Lock'"


@pytest.mark.xfail(
    reason="https://github.com/ITISFoundation/osparc-simcore/issues/9820",
    raises=AssertionError,
    strict=True,
)
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_patch_node_does_not_deadlock_with_a_concurrent_graph_patch(
    mock_dynamic_scheduler: None,
    mocked_dynamic_services_interface: dict[str, mock.MagicMock],
    client: TestClient,
    user_project: ProjectDict,
    postgres_db: sa.engine.Engine,
    mocker: MockerFixture,
):
    assert client.app
    node_id = next(iter(user_project["workbench"]))
    url = client.app.router["patch_project_node"].url_for(project_id=user_project["uuid"], node_id=node_id)

    # the graph PATCH holds the `projects` row lock until the test lets it write the node
    original_lock_project_graph = _projects_repository._lock_project_graph  # noqa: SLF001
    graph_locked = asyncio.Event()
    release_graph_patch = asyncio.Event()

    async def _lock_project_graph(connection: AsyncConnection, *, project_uuid: ProjectID) -> None:
        await original_lock_project_graph(connection, project_uuid=project_uuid)
        graph_locked.set()
        await release_graph_patch.wait()

    mocker.patch.object(_projects_repository, "_lock_project_graph", side_effect=_lock_project_graph)

    def _count_lock_waiters() -> int:
        with postgres_db.connect() as conn:
            waiters: Any = conn.scalar(sa.text(_SOMEONE_WAITS_FOR_A_LOCK_SQL))
            return int(waiters)

    graph_patch = asyncio.create_task(client.patch(url.path, json={"inputs": {"in_1": 42}}))
    await asyncio.wait_for(graph_locked.wait(), timeout=_TIMEOUT_S)

    # same node, no graph field: its UPDATE takes the node row, then waits for the `projects` row
    label_patch = asyncio.create_task(client.patch(url.path, json={"label": "relabelled"}))
    async for attempt in AsyncRetrying(
        stop=stop_after_delay(_TIMEOUT_S),
        wait=wait_fixed(0.05),
        retry=retry_if_exception_type(AssertionError),
        reraise=True,
    ):
        with attempt:
            assert _count_lock_waiters() > 0, "the node PATCH never waited for the graph PATCH"

    release_graph_patch.set()

    # both run to the end, so that a deadlock shows up as a 500 instead of a hang
    responses: list[ClientResponse] = await asyncio.wait_for(
        asyncio.gather(graph_patch, label_patch), timeout=_TIMEOUT_S
    )
    for response in responses:
        await assert_status(response, status.HTTP_204_NO_CONTENT)
