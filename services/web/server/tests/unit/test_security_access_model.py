# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

#
import copy
import difflib
import json

# https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1
#
from typing import Callable, Dict, List

import attr
import jsondiff
import pytest
from aiohttp import web

from simcore_service_webserver.resources import resources
from simcore_service_webserver.security_access_model import (
    RoleBasedAccessModel,
    check_access,
)
from simcore_service_webserver.security_permissions import and_, or_
from simcore_service_webserver.security_roles import ROLES_PERMISSIONS, UserRole


@pytest.fixture
def access_model():
    def can_update_inputs(context):
        current_data = context["current"]
        candidate_data = context["candidate"]

        diffs = jsondiff.diff(current_data, candidate_data)

        if "workbench" in diffs:
            try:
                for node in diffs["workbench"]:
                    # can ONLY modify `inputs` fields set as ReadAndWrite
                    access = current_data["workbench"][node]["inputAccess"]
                    inputs = diffs["workbench"][node]["inputs"]
                    for key in inputs:
                        if access.get(key) != "ReadAndWrite":
                            return False
                    return True
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
                    "check": can_update_inputs,
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
    rbac = RoleBasedAccessModel.from_rawdata(fake_roles_permissions)
    return rbac


# TESTS -------------------------------------------------------------------------


def test_roles():
    super_users = UserRole.super_users()
    assert super_users
    assert UserRole.USER not in super_users
    assert all(r in UserRole for r in super_users)


def test_unique_permissions():
    # Limit for scalability. Test that unnecessary resources and/or actions are used
    # Enforce reusable permission layouts
    # TODO: limit the actions "read"
    # TODO: limit the resouces "read"

    used = []
    for role in ROLES_PERMISSIONS:
        can = ROLES_PERMISSIONS[role].get("can", [])
        for permission in can:
            assert permission not in used, (
                "'%s' in %s is repeated in security_roles.ROLES_PERMISSIONS"
                % (permission, role)
            )
            used.append(permission)


def test_access_model_loads():
    access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)

    roles_with_permissions = set(access_model.roles.keys())
    all_roles = set(UserRole)

    assert not all_roles.difference(roles_with_permissions)


async def test_named_permissions(access_model):

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


async def test_permissions_inheritance(access_model):
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


@pytest.mark.skip(reason="REVIEW")
async def test_checked_permissions(access_model):
    R = UserRole  # alias
    MOCKPATH = "data/fake-template-projects.json"

    with resources.stream(MOCKPATH) as fh:
        data = json.load(fh)

    current = {}
    for prj in data:
        if prj["uuid"] == "template-uuid-1234-a1a7-f7d4f3a8f26b":
            current = prj
            break

    assert current, "Did '%s' changed??" % MOCKPATH

    # updates both allowed and not allowed fields
    candidate = copy.deepcopy(current)
    candidate["workbench"]["template-uuid-409d-998c-c1f04de67f8b"]["inputs"][
        "Kr"
    ] = 66  # ReadOnly!
    candidate["workbench"]["template-uuid-409d-998c-c1f04de67f8b"]["inputs"][
        "Na"
    ] = 66  # ReadWrite

    assert not await access_model.can(
        R.ANONYMOUS,
        "study.pipeline.node.inputs.update",
        context={"current": current, "candidate": candidate},
    )

    # updates allowed fields
    candidate = copy.deepcopy(current)
    candidate["workbench"]["template-uuid-409d-998c-c1f04de67f8b"]["inputs"][
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


async def test_async_checked_permissions(access_model):
    R = UserRole  # alias

    # add checked permissions
    async def async_callback(context) -> bool:
        return context["response"]

    access_model.roles[R.TESTER].check["study.edge.edit"] = async_callback

    assert not await access_model.can(
        R.TESTER, "study.edge.edit", context={"response": False}
    )

    assert await access_model.can(
        R.TESTER, "study.edge.edit", context={"response": True}
    )


async def test_check_access_expressions(access_model):
    R = UserRole

    assert await check_access(access_model, R.ANONYMOUS, "study.stop")

    assert await check_access(
        access_model, R.ANONYMOUS, "study.stop |study.node.create"
    )

    assert not await check_access(
        access_model, R.ANONYMOUS, "study.stop & study.node.create"
    )

    assert await check_access(access_model, R.USER, "study.stop & study.node.create")

    # TODO: extend expression parser
    # assert await check_access(access_model, R.USER,
    #    "study.stop & (study.node.create|study.nodestree.uuid.read)")

    # assert await check_access(access_model, R.TESTER,
    #    "study.stop & study.node.create & study.nodestree.uuid.read")
