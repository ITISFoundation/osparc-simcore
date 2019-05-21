# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

#
# https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1
#
from typing import Callable, Dict, List

import attr
import pytest
from aiohttp import web

from simcore_service_webserver.security_access_model import (
    RoleBasedAccessModel, check_access)
from simcore_service_webserver.security_permissions import and_, or_
from simcore_service_webserver.security_roles import (ROLES_PERMISSIONS,
                                                      UserRole)


@pytest.fixture
def access_model():
    fake_roles_permissions = {
        UserRole.ANONYMOUS: {
            'can': [
                "studies.templates.read",
                "study.start",
                "study.stop",
                "study.update"
            ]
        },
        UserRole.USER: {
            'can': [
                "study.node.create",
                "study.node.delete",
                "study.node.rename",
                "study.node.start",
                "study.node.data.push",
                "study.node.data.delete",
                "study.edge.create",
                "study.edge.delete"
            ],
            'inherits': [UserRole.ANONYMOUS]
        },
        UserRole.TESTER: {
            'can': [
                "study.nodestree.uuid.read",
                "study.logger.debug.read"
            ],
             # This double inheritance is done intentionally redundant
            'inherits': [UserRole.USER, UserRole.ANONYMOUS]
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
    assert all( r in UserRole for r in super_users )


def test_unique_permissions():
    # Limit for scalability. Test that unnecessary resources and/or actions are used
    # Enforce reusable permission layouts
    # TODO: limit the actions "read"
    # TODO: limit the resouces "read"

    used = []
    for role in ROLES_PERMISSIONS:
        can = ROLES_PERMISSIONS[role].get("can", [])
        for permission in can:
            assert permission not in used, "'%s' in %s is repeated in security_roles.ROLES_PERMISSIONS" % (permission, role)
            used.append(permission)


def test_access_model_loads():
    access_model = RoleBasedAccessModel.from_rawdata(ROLES_PERMISSIONS)

    roles_with_permissions = set(access_model._roles.keys())
    all_roles = set(UserRole)

    assert not all_roles.difference(roles_with_permissions)


async def test_named_permissions(access_model):

    R = UserRole # alias

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


async def test_checked_permissions(access_model):
    R = UserRole # alias

    # add checked permissions
    def sync_callback(context) -> bool:
        return context['response']

    access_model._roles[R.TESTER].check['study.edge.edit'] = sync_callback

    assert not await access_model.can(
        R.TESTER,
        "study.edge.edit",
        context={'response':False}
    )

    assert await access_model.can(
        R.TESTER,
        "study.edge.edit",
        context={'response':True}
    )


async def test_async_checked_permissions(access_model):
    R = UserRole # alias

    # add checked permissions
    async def async_callback(context) -> bool:
        return context['response']

    access_model._roles[R.TESTER].check['study.edge.edit'] = async_callback

    assert not await access_model.can(
        R.TESTER,
        "study.edge.edit",
        context={'response':False}
    )

    assert await access_model.can(
        R.TESTER,
        "study.edge.edit",
        context={'response':True}
    )


async def test_check_access_expressions(access_model):
    R = UserRole

    assert await check_access(access_model, R.ANONYMOUS, "study.stop")

    assert await check_access(access_model, R.ANONYMOUS,
        or_("study.stop", "study.node.create"))

    assert not await check_access(access_model, R.ANONYMOUS,
        and_("study.stop", "study.node.create"))

    assert await check_access(access_model, R.USER,
        and_("study.stop", "study.node.create"))

    assert await check_access(access_model, R.USER,
        and_("study.stop", or_("study.node.create", "study.nodestree.uuid.read")))

    assert await check_access(access_model, R.TESTER,
        and_("study.stop", and_("study.node.create", "study.nodestree.uuid.read")))
