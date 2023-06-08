""" hierarchical role-based access control (HRBAC)


   References:
    https://b_logger.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1
"""

import inspect
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, TypeAlias

from ..db.models import UserRole

_logger = logging.getLogger(__name__)

ContextType: TypeAlias = Optional[dict[str, Any]]


@dataclass
class _RolePermissions:
    role: UserRole
    # named permissions allowed
    allowed: list[str] = field(default_factory=list)
    # checked permissions: permissions with conditions
    check: dict[str, Callable[[ContextType], bool]] = field(default_factory=dict)
    inherits: list[UserRole] = field(default_factory=list)

    @classmethod
    def from_rawdata(cls, role: str | UserRole, value: dict) -> "_RolePermissions":

        if isinstance(role, str):
            name = role
            role = UserRole[name]

        role_permission = cls(role=role, inherits=value.get("inherits", []))

        allowed = set()
        check = {}
        for item in value.get("can", []):
            if isinstance(item, dict):
                check[item["name"]] = item["check"]
            elif isinstance(item, str):
                allowed.add(item)
            else:
                raise ValueError(f"Unexpected item for role '{role}'")

        role_permission.allowed = list(allowed)
        role_permission.check = check
        return role_permission


class RoleBasedAccessModel:
    """Role-based access control model

    - All role permissions get registered here
    - Access point to check for permissions on a given operation within a context (passed to check function)

    - For checks with operation expressions (e.g. can operation A & operation B?) see check_access free function below

    """

    def __init__(self, roles: list[_RolePermissions]):
        self.roles: dict[UserRole, _RolePermissions] = {r.role: r for r in roles}

    async def can(
        self, role: UserRole, operation: str, context: ContextType = None
    ) -> bool:
        # pylint: disable=too-many-return-statements

        # undefined operation
        if not operation:
            _logger.debug("Checking undefined operation %s in access model", operation)
            return False

        # undefined role
        role_access = self.roles.get(role, None)
        if not role_access:
            _logger.debug("Role %s has no permissions defined in acces model", role)
            return False

        # check named operations
        if operation in role_access.allowed:
            return True

        # checked operations
        if operation in role_access.check.keys():
            check = role_access.check[operation]
            try:
                is_valid: bool

                if inspect.iscoroutinefunction(check):
                    is_valid = await check(context)
                    return is_valid

                is_valid = check(context)
                return is_valid

            except Exception:  # pylint: disable=broad-except
                _logger.debug(
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

    async def who_can(self, operation: str, context: dict | None = None):
        allowed = []
        for role in self.roles:
            if await self.can(role, operation, context):
                allowed.append(role)
        return allowed

    @classmethod
    def from_rawdata(cls, raw: dict):
        roles = [
            _RolePermissions.from_rawdata(role, value) for role, value in raw.items()
        ]
        return RoleBasedAccessModel(roles)


_OPERATORS_REGEX_PATTERN = re.compile(r"(&|\||\bAND\b|\bOR\b)")


async def check_access(
    model: RoleBasedAccessModel, role: UserRole, operations: str, context: dict = None
) -> bool:
    """Extends `RoleBasedAccessModel.can` to check access to boolean expressions of operations

    Returns True if a user with a role has permission on a given context
    """
    tokens = _OPERATORS_REGEX_PATTERN.split(operations)
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

    raise NotImplementedError(
        f"Invalid expression '{operations}': only supports at most two operands"
    )
