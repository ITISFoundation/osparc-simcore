# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""CHARACTERIZATION TESTS pinning the pricing/resources state of the database
(see `pytest_simcore.helpers.project_nodes_pricing`):

- `projects_nodes.required_resources`
- `projects_node_to_pricing_unit`

These tests describe the STATE produced by project creation, not the code that
produces it, so they keep passing while the responsibility for writing that state
moves from director-v2 to the web-server (pricing/resources ownership rework).
Tests marked `@pytest.mark.epic(...)` assert TODAY's behaviour and name, in their
docstring, the PR of the epic intended to change them (`flips_in`).

The dynamic-node "linked + sized with the dynamic formula at dynamic start" and
the computational-node "linked to the default unit + sized on the first pipeline
update" behaviors are exercised from the director-v2 side in
`services/director-v2/tests/unit/with_dbs` (D1-D6).
"""

import pytest
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.project_nodes_pricing import get_node_pricing_state
from pytest_simcore.helpers.webserver_users import UserInfoDict
from simcore_service_webserver.db.models import UserRole
from simcore_service_webserver.projects.models import ProjectDict
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.mark.epic("sanderegg/9851", flips_in="PR2")
@pytest.mark.parametrize("user_role", [UserRole.USER])
async def test_project_creation_writes_no_pricing_links(
    client: TestClient,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    asyncpg_engine: AsyncEngine,
):
    """W5: creating a project (new, copy, template or api-server job) writes
    `projects_nodes` rows but NEVER a `projects_node_to_pricing_unit` link, and
    makes no resource-usage-tracker call (none is mocked here and aioresponses
    would raise on an unexpected HTTP call).

    ⚠️ The pricing/resources ownership rework (PR 2) intends to link the default
    pricing unit and size COMPUTATIONAL nodes at creation; when that lands,
    computational nodes here must be expected to have a default link and
    dask-sized resources (dynamic/frontend nodes keep having no link).
    """
    assert client.app

    state = await get_node_pricing_state(asyncpg_engine, user_project["uuid"])
    assert state, "the test project must have persisted nodes"

    for node_state in state.values():
        assert node_state.pricing_plan_id is None
        assert node_state.pricing_unit_id is None
