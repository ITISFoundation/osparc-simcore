from enum import Enum
from functools import total_ordering

_USER_ROLE_TO_LEVEL = {
    "ANONYMOUS": 0,
    "GUEST": 10,
    "USER": 20,
    "TESTER": 30,
    "PRODUCT_OWNER": 40,
    "ADMIN": 100,
}


@total_ordering
class UserRole(Enum):
    """SORTED enumeration of user roles

    A role defines a set of privileges the user can perform
    Roles are sorted from lower to highest privileges
    USER is the role assigned by default A user with a higher/lower role is denoted super/infra user

    ANONYMOUS : The user is not logged in
    GUEST     : Temporary user with very limited access. Main used for demos and for a limited amount of time
    USER      : Registered user. Basic permissions to use the platform [default]
    TESTER    : Upgraded user. First level of super-user with privileges to test the framework.
                Can use everything but does not have an effect in other users or actual data
    ADMIN     : Framework admin.

    See security_access.py
    """

    ANONYMOUS = "ANONYMOUS"
    GUEST = "GUEST"
    USER = "USER"
    TESTER = "TESTER"
    PRODUCT_OWNER = "PRODUCT_OWNER"
    ADMIN = "ADMIN"

    @property
    def privilege_level(self) -> int:
        return _USER_ROLE_TO_LEVEL[self.name]

    def __lt__(self, other: "UserRole") -> bool:
        if self.__class__ is other.__class__:
            return self.privilege_level < other.privilege_level
        return NotImplemented


class UserStatus(str, Enum):
    # This is a transition state. The user is registered but not confirmed. NOTE that state is optional depending on LOGIN_REGISTRATION_CONFIRMATION_REQUIRED
    CONFIRMATION_PENDING = "CONFIRMATION_PENDING"
    # This user can now operate the platform
    ACTIVE = "ACTIVE"
    # This user is inactive because it expired after a trial period
    EXPIRED = "EXPIRED"
    # This user is inactive because he has been a bad boy
    BANNED = "BANNED"
    # This user is inactive because it was marked for deletion
    DELETED = "DELETED"


class AccountRequestStatus(str, Enum):
    """Status of the request for an account"""

    PENDING = "PENDING"  # Pending PO review to approve/reject the request
    APPROVED = "APPROVED"  # PO approved the request
    REJECTED = "REJECTED"  # PO rejected the request
