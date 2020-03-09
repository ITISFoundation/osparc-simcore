""" hierarchical role-based access control (HRBAC)


   References:
    https://blog.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1
"""

import inspect
import logging
import re
from typing import Callable, Dict, List

import attr

from .db_models import UserRole

log = logging.getLogger(__file__)


@attr.s(auto_attribs=True)
class RolePermissions:
    role: UserRole
    allowed: List[str] = attr.Factory(list)  # named permissions allowed
    check: Dict[str, Callable[[], bool]] = attr.Factory(
        dict
    )  # checked permissions: permissions with conditions
    inherits: List[str] = attr.Factory(list)

    @classmethod
    def from_rawdata(cls, role, value: Dict):

        if isinstance(role, str):
            name = role
            role = UserRole[name]

        role = RolePermissions(
            role=role, allowed=[], check=[], inherits=value.get("inherits", [])
        )

        allowed = set()
        check = dict()
        for item in value.get("can", list()):
            if isinstance(item, Dict):
                check[item["name"]] = item["check"]
            elif isinstance(item, str):
                allowed.add(item)
            else:
                raise ValueError("Unexpected item for role '{}'".format(name))

        role.allowed = list(allowed)
        role.check = check
        return role


class RoleBasedAccessModel:
    """ Role-based access control model

    - All role permissions get registered here
    - Access point to check for permissions on a given operation within a context (passed to check function)

    - For checks with operation expressions (e.g. can operation A & operation B?) see check_access free function below

    """

    def __init__(self, roles: List[RolePermissions]):
        self.roles = {r.role: r for r in roles}

    # TODO: all operations allowed for a given role
    # TODO: build a tree out of the list of allowed operations
    # TODO: operations to ADD/REMOVE/EDIT permissions in a role

    async def can(self, role: UserRole, operation: str, context: Dict = None) -> bool:
        # pylint: disable=too-many-return-statements

        # undefined operation  TODO: check if such a name is defined??
        if not operation:
            log.debug("Checking undefined operation %s in access model", operation)
            return False

        # undefined role
        role_access = self.roles.get(role, False)
        if not role_access:
            log.debug("Role %s has no permissions defined in acces model", role)
            return False

        # check named operations
        # TODO: add wildcards???
        if operation in role_access.allowed:
            return True

        # checked operations
        if operation in role_access.check.keys():
            check = role_access.check[operation]
            try:
                if inspect.iscoroutinefunction(check):
                    return await check(context)
                return check(context)
            except Exception:  # pylint: disable=broad-except
                log.exception(
                    "Check operation '%s', shall not raise [%s]", operation, check
                )
                return False

        # check if any parents
        if not role_access.inherits:
            return False

        for parent in role_access.inherits:
            if await self.can(parent, operation, context):
                return True
        return False

    async def who_can(self, operation: str, context: Dict = None):
        allowed = []
        for role in self.roles:
            if await self.can(role, operation, context):
                allowed.append(role)
        return allowed

    @classmethod
    def from_rawdata(cls, raw: Dict):
        roles = [
            RolePermissions.from_rawdata(role, value) for role, value in raw.items()
        ]
        return RoleBasedAccessModel(roles)

    # TODO: print table??


# TODO: implement expression parser: reg = re.compile(r'(&|\||\bAND\b|\bOR\b|\(|\))')
operators_pattern = re.compile(r"(&|\||\bAND\b|\bOR\b)")


async def check_access(
    model: RoleBasedAccessModel, role: UserRole, operations: str, context: Dict = None
) -> bool:
    """ Extends `RoleBasedAccessModel.can` to check access to boolean expressions of operations

        Returns True if a user with a role has permission on a given context
    """
    tokens = operators_pattern.split(operations)
    if len(tokens) == 1:
        return await model.can(role, tokens[0], context)

    if len(tokens) == 3:
        tokens = [t.strip() for t in tokens if t.strip() != ""]
        lhs, op, rhs = tokens
        can_lhs = await model.can(role, lhs, context)
        if op in ["AND", "&"]:
            if can_lhs:
                return await model.can(role, rhs, context)
            return False
        return can_lhs or (await model.can(role, rhs, context))

    # FIXME: This only works for operators with TWO operands
    raise NotImplementedError("Invalid expression %s" % operations)
