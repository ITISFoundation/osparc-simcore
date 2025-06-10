# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


# REFERENCES
#   https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock

import jsondiff
import pytest
from aiocache.base import BaseCache
from aiohttp import web
from psycopg2 import DatabaseError
from pytest_mock import MockerFixture
from simcore_service_webserver.projects.models import ProjectDict
from simcore_service_webserver.security._authz_access_model import (
    RoleBasedAccessModel,
    has_access_by_role,
)
from simcore_service_webserver.security._authz_access_roles import (
    ROLES_PERMISSIONS,
    UserRole,
)
from simcore_service_webserver.security._authz_policy import AuthorizationPolicy
from simcore_service_webserver.security._authz_repository import AuthInfoDict


@pytest.fixture
def access_model() -> RoleBasedAccessModel:
    def _can_update_inputs(context):
        current_data = context["current"]
        candidate_data = context["candidate"]

        diffs = jsondiff.diff(current_data, candidate_data)

        if "workbench" in diffs:
            try:
                for node in diffs["workbench"]:
                    # can ONLY modify `inputs` fields set as ReadAndWrite
                    access = current_data["workbench"][node]["inputAccess"]
                    inputs = diffs["workbench"][node]["inputs"]
                    return all(access.get(key) == "ReadAndWrite" for key in inputs)
            except KeyError:
                pass
            return False

        return len(diffs) == 0  # no changes

    # -----------
    fake_roles_permissions = {
        UserRole.ANONYMOUS: {
            "can": [
                "studies.templates.read",
                "study.start",
                "study.stop",
                {
                    "name": "study.pipeline.node.inputs.update",
                    "check": _can_update_inputs,
                },
            ]
        },
        UserRole.USER: {
            "can": [
                "study.node.create",
                "study.node.delete",
                "study.node.rename",
                "study.node.start",
                "study.node.data.push",
                "study.node.data.delete",
                "study.edge.create",
                "study.edge.delete",
            ],
            "inherits": [UserRole.ANONYMOUS],
        },
        UserRole.TESTER: {
            "can": ["study.nodestree.uuid.read", "study.logger.debug.read"],
            # This double inheritance is done intentionally redundant
            "inherits": [UserRole.USER, UserRole.ANONYMOUS],
        },
    }

    # RBAC: Role Based Access Control
    return RoleBasedAccessModel.from_rawdata(fake_roles_permissions)


def test_unique_permissions():
    used = []
    for role in ROLES_PERMISSIONS:
        can = ROLES_PERMISSIONS[role].get("can", [])
        for permission in can:
            assert (
                permission not in used
            ), f"'{permission}' in {role} is repeated in security_roles.ROLES_PERMISSIONS"
            used.append(permission)


def test_access_model_loads():
    access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)

    roles_with_permissions = set(access_model.roles.keys())
    all_roles = set(UserRole)

    assert not all_roles.difference(roles_with_permissions)


async def test_named_permissions(access_model: RoleBasedAccessModel):

    R = UserRole  # alias

    # direct permission
    assert await access_model.can(R.USER, "study.edge.delete")
    assert not await access_model.can(R.ANONYMOUS, "study.edge.delete")

    # inherited
    assert await access_model.can(R.TESTER, "study.edge.delete")
    assert await access_model.can(R.ANONYMOUS, "studies.templates.read")

    who_can_delete = await access_model.who_can("study.edge.delete")
    assert R.USER in who_can_delete
    assert R.TESTER in who_can_delete


async def test_permissions_inheritance(access_model: RoleBasedAccessModel):
    # ANONYMOUS <--- USER <--- TESTER

    R = UserRole

    OPERATION = "studies.templates.read"
    assert await access_model.can(R.ANONYMOUS, OPERATION)
    assert await access_model.can(R.USER, OPERATION)
    assert await access_model.can(R.TESTER, OPERATION)

    OPERATION = "study.node.create"
    assert not await access_model.can(R.ANONYMOUS, OPERATION)
    assert await access_model.can(R.USER, OPERATION)
    assert await access_model.can(R.TESTER, OPERATION)

    OPERATION = "study.nodestree.uuid.read"
    assert not await access_model.can(R.ANONYMOUS, OPERATION)
    assert not await access_model.can(R.USER, OPERATION)
    assert await access_model.can(R.TESTER, OPERATION)

    OPERATION = "study.amazing.action"
    assert not await access_model.can(R.ANONYMOUS, OPERATION)
    assert not await access_model.can(R.USER, OPERATION)
    assert not await access_model.can(R.TESTER, OPERATION)


async def test_checked_permissions(
    access_model: RoleBasedAccessModel, tests_data_dir: Path
):
    R = UserRole  # alias

    current: ProjectDict = json.loads(
        (tests_data_dir / "fake-template-projects.isan.ucdavis.json").read_text()
    )
    assert (
        current["uuid"] == "de2578c5-431e-1234-a1a7-f7d4f3a8f26b"
    ), "Did uuids of the fake changed"

    # updates both allowed and not allowed fields
    candidate = copy.deepcopy(current)
    candidate["workbench"]["de2578c5-431e-409d-998c-c1f04de67f8b"]["inputs"][
        "Kr"
    ] = 66  # ReadOnly!
    candidate["workbench"]["de2578c5-431e-409d-998c-c1f04de67f8b"]["inputs"][
        "Na"
    ] = 66  # ReadWrite

    assert not await access_model.can(
        R.ANONYMOUS,
        "study.pipeline.node.inputs.update",
        context={"current": current, "candidate": candidate},
    )

    # updates allowed fields
    candidate = copy.deepcopy(current)
    candidate["workbench"]["de2578c5-431e-409d-998c-c1f04de67f8b"]["inputs"][
        "Na"
    ] = 66  # ReadWrite

    assert await access_model.can(
        R.ANONYMOUS,
        "study.pipeline.node.inputs.update",
        context={"current": current, "candidate": candidate},
    )

    # udpates not permitted fields
    candidate = copy.deepcopy(current)
    candidate["description"] = "not allowed to write here"
    assert not await access_model.can(
        R.ANONYMOUS,
        "study.pipeline.node.inputs.update",
        context={"current": current, "candidate": candidate},
    )


async def test_async_checked_permissions(access_model: RoleBasedAccessModel):
    R = UserRole  # alias

    # add checked permissions
    async def async_callback(context) -> bool:
        return context["response"]

    assert access_model.roles[R.TESTER]
    access_model.roles[R.TESTER].check["study.edge.edit"] = async_callback

    assert not await access_model.can(
        R.TESTER, "study.edge.edit", context={"response": False}
    )

    assert await access_model.can(
        R.TESTER, "study.edge.edit", context={"response": True}
    )


async def test_check_access_expressions(access_model: RoleBasedAccessModel):
    R = UserRole

    assert await has_access_by_role(access_model, R.ANONYMOUS, "study.stop")

    assert await has_access_by_role(
        access_model, R.ANONYMOUS, "study.stop |study.node.create"
    )

    assert not await has_access_by_role(
        access_model, R.ANONYMOUS, "study.stop & study.node.create"
    )

    assert await has_access_by_role(
        access_model, R.USER, "study.stop & study.node.create"
    )


@pytest.fixture
def mock_db(mocker: MockerFixture) -> MagicMock:

    mocker.patch(
        "simcore_service_webserver.security._authz_policy.get_async_engine",
        autospec=True,
        return_value="FAKE-ENGINE",
    )

    users_db: dict[str, AuthInfoDict] = {
        "foo@email.com": AuthInfoDict(id=1, role=UserRole.GUEST),
        "bar@email.com": AuthInfoDict(id=55, role=UserRole.GUEST),
    }

    async def _fake_db(engine, email):
        assert engine == "FAKE-ENGINE"

        if "db-failure" in email:
            raise DatabaseError

        # inactive user or not found
        return copy.deepcopy(users_db.get(email))

    mock_db_fun = mocker.patch(
        "simcore_service_webserver.security._authz_policy.get_active_user_or_none",
        autospec=True,
        side_effect=_fake_db,
    )

    mock_db_fun.users_db = users_db
    return mock_db_fun


async def test_authorization_policy_cache(mocker: MockerFixture, mock_db: MagicMock):

    app = web.Application()
    authz_policy = AuthorizationPolicy(app, RoleBasedAccessModel([]))

    # cache under test

    # pylint: disable=no-member
    autz_cache: BaseCache = authz_policy._get_auth_or_none.cache

    assert not (await autz_cache.exists("_get_auth_or_none/foo@email.com"))
    for _ in range(3):
        got = await authz_policy._get_auth_or_none(email="foo@email.com")
        assert mock_db.call_count == 1
        assert got["id"] == 1

    assert await autz_cache.exists("_get_auth_or_none/foo@email.com")

    # new value in db
    mock_db.users_db["foo@email.com"]["id"] = 2
    assert (await autz_cache.get("_get_auth_or_none/foo@email.com"))["id"] == 1

    # gets cache, db is NOT called
    got = await authz_policy._get_auth_or_none(email="foo@email.com")
    assert mock_db.call_count == 1
    assert got["id"] == 1

    # clear cache
    await authz_policy.clear_cache()

    # gets new value
    got = await authz_policy._get_auth_or_none(email="foo@email.com")
    assert mock_db.call_count == 2
    assert got["id"] == 2

    # other email has other key
    assert not (await autz_cache.exists("_get_auth_or_none/bar@email.com"))

    for _ in range(4):
        # NOTE: None
        assert await authz_policy._get_auth_or_none(email="bar@email.com")
        assert await autz_cache.exists("_get_auth_or_none/bar@email.com")
        assert mock_db.call_count == 3

    # should raise web.HTTPServiceUnavailable on db failure
    with pytest.raises(web.HTTPServiceUnavailable):
        await authz_policy._get_auth_or_none(email="db-failure@email.com")
