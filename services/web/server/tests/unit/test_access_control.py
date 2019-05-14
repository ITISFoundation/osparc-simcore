# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

#
# https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1
#
from typing import Callable, Dict, List

import attr
import pytest
from aiohttp import web


@attr.s(auto_attribs=True)
class Role(object):
    name: str
    allowed: List[str]=attr.Factory(list) # named permissions allowed
    check: Dict[str, Callable[[web.Request],bool]]=attr.Factory(dict) # permissions with conditions
    inherits: List[str]=attr.Factory(list)

    @classmethod
    def fromrawdata(cls, name, value:Dict):
        role = Role(name=name, allowed=[], check=[], inherits=value.get('inherits', []))

        allowed = set()
        check = dict()
        for item in value.get('can', list()):
            if isinstance(item, Dict):
                check[item['name']] = item['check']
            elif isinstance(item, str):
                allowed.add(item)
            else:
                raise ValueError("Unexpcted item for role '{}'".format(name))

        role.allowed = list(allowed)
        role.check = check
        return role

class RoleBaseAccessModel:
    def __init__(self, roles: List[Role]):
        # Assert right roles
        self._roles = {r.name:r for r in roles}

    async def can(self, role: str, operation: str, context=None) -> bool:
        # undefined operation  TODO: check if such a name is defined??
        if not operation:
            return False

        # undefined role
        role_obj = self._roles.get(role, False)
        if not role_obj:
            return False

        # check named operations
        # TODO: add wildcards???
        if operation in role_obj.allowed:
            return True

        # checked operations
        if operation in role_obj.check:
            if await role_obj.check(context):
                return True

        # check if any parents
        if not role_obj.inherits:
            return False

        for parent in role_obj.inherits:
            if await self.can(parent, operation, context):
                return True
        return False

    async def who(self, operation: str, context=None):
        roles = []
        for role in self._roles:
            roles.append( await self.can(role, operation, context) )
        return roles

    # TODO: who can do operation A and not operation A.*.C ?
    # TODO: all operations allowed for a given role
    # TODO: build a tree out of the list of allowed operations

    def get_defined_operations(self):
        names = set()
        for role in self._roles.values():
            names = names.union( set(role.allowed + [c.name for c in role.check]) )
        return list(names)



#-------------------------
#from aiohttp import web
#from aiohttp_session import check_permission



#async def handler_something(context):
#    await check_permission(context, 'studies.user.read')


@pytest.fixture
def list_of_roles():

    # operations are defined as a hierachical namespaces
    # resources hierarchy and a final verb for an action, e.g. read, write, edit, ...
    # roles list allowed operations under "can"
    # a role can inherit the allowed operations of a parent.
    # can use this to extend the list of allowed operations

    # in db ??
    # if some permissions are not used it's not so serious
    # TODO: wildcards to label operations
    _roles = {
        'anonymous': {
            'can': [
                "studies.templates.read",
                "study.node.data.pull",
                "study.start",
                "study.stop",
                "study.update"
            ]
        },
        'user': {
            'can': [
                "studies.user.read",
                "studies.user.create",
                "storage.datcore.read",
                "preferences.user.update",
                "preferences.token.create",
                "preferences.token.delete",
                "study.node.create",
                "study.node.delete",
                "study.node.rename",
                "study.node.start",
                "study.node.data.push",
                "study.node.data.delete",
                "study.edge.create",
                "study.edge.delete"
            ],
            'inherits': ['anonymous']
        },
        'tester': {
            'can': [
                "services.all.read",
                "preferences.role.update",
                "study.nodestree.uuid.read",
                "study.logger.debug.read"
            ],
            'inherits': ['user', 'anonymous']
        },
        'admin': {
            'can': [],
            'inherits': ['tester', 'user', 'anonymous']
        },
    }

    roles = [Role.fromrawdata(name, value) for name, value in _roles.items()]
    return roles


# RBAC: Role Based Access Control
async def test_it(list_of_roles):
    access_model = RoleBaseAccessModel(list_of_roles)

    # direct permission
    assert await access_model.can("user", "study.edge.delete")
    assert not await access_model.can("anonymous", "study.edge.delete")

    # inherited
    assert await access_model.can("tester", "study.edge.delete")
    assert await access_model.can("anonymous", "studies.templates.read")

    # some extra operations
    operations = access_model.get_defined_operations()
    assert len(operations) == sum(len(role.allowed) for role in list_of_roles)


    # permits(request, permission, context=None)
    # - permission needs to be a str or an enum.Enum
    # - request is identified -> user's email
    # - DBAuthorizationPolicy.permits(identity, permission, context) -> detetermins the access
