"""hierarchical role-based access control (HRBAC)


References:
 https://b_logger.nodeswat.com/implement-access-control-in-node-js-8567e7b484d1
"""

import inspect
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import TypeAlias, TypedDict

from models_library.products import ProductName
from models_library.users import UserID

from ..db.models import UserRole

_logger = logging.getLogger(__name__)


class AuthContextDict(TypedDict, total=False):
    authorized_uid: UserID
    product_name: ProductName


OptionalContext: TypeAlias = AuthContextDict | dict | None

CheckFunction: TypeAlias = (
    # Type for check functions that can be either sync or async
    Callable[[OptionalContext], bool]
    | Callable[[OptionalContext], Awaitable[bool]]
)


@dataclass
class _RolePermissions:
    role: UserRole

    allowed: list[str] = field(
        default_factory=list, metadata={"description": "list of allowed operations"}
    )
    check: dict[str, CheckFunction] = field(
        default_factory=dict,
        metadata={
            "description": "checked permissions: dict of operations with conditions"
        },
    )
    inherits: list[UserRole] = field(
        default_factory=list,
        metadata={
            "description": "list of parent roles that inherit permissions from this role"
        },
    )

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
                msg = f"Unexpected item for role '{role}'"
                raise TypeError(msg)

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
        self, role: UserRole, operation: str, context: OptionalContext = None
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
        if operation in role_access.check:
            check = role_access.check[operation]
            try:
                ok: bool
                if inspect.iscoroutinefunction(check):
                    ok = await check(context)
                else:
                    ok = check(context)
                return ok

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

    async def who_can(self, operation: str, context: OptionalContext = None):
        return [role for role in self.roles if await self.can(role, operation, context)]

    @classmethod
    def from_rawdata(cls, raw: dict):
        roles = [
            _RolePermissions.from_rawdata(role, value) for role, value in raw.items()
        ]
        return RoleBasedAccessModel(roles)


async def has_access_by_role(
    model: RoleBasedAccessModel,
    role: UserRole,
    operation: str,
    context: OptionalContext = None,
) -> bool:
    return await model.can(role=role, operation=operation, context=context)
