# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Any, Type

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.utils_assert import assert_status
from simcore_service_webserver.db_models import UserRole


@pytest.mark.parametrize(
    "user_role,expected_response_cls",
    [
        (UserRole.ANONYMOUS, web.HTTPUnauthorized),
        (UserRole.GUEST, web.HTTPUnauthorized),
        (UserRole.USER, web.HTTPOk),
        (UserRole.TESTER, web.HTTPOk),
    ],
)
async def test_clone_project_with_role(
    client: TestClient,
    user_role: UserRole,
    user_project: dict[str, Any],
    expected_response_cls: Type[web.HTTPException],
):
    """tests role-based access to clone_project"""
    src_project_id = user_project["uuid"]

    resp = await client.post(f"/projects/{src_project_id}:clone")
    data, errors = await assert_status(resp, expected_response_cls)

    if data:
        # check: project db clone is correct
        # check: storage s3 clone is correct
        raise NotImplementedError


async def test_clone_project_with_group():
    """tests group-based access to clone_project"""
    raise NotImplementedError


async def test_error_while_clone_project():
    # action: clone
    # event: fail while cloning
    # check: does not leave any residues in database or s3. All gets cancelled
    raise NotImplementedError


async def test_long_operation_error_project():
    raise NotImplementedError
