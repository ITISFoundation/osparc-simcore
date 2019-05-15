""" Defines different user roles and its associated permission

    This definition is consumed by the security_access_model to build an access model for the framework
    The access model is created upon setting up of the security subsystem
"""
import itertools
from enum import Enum
from typing import List, Tuple


class UserRole(Enum):
    """ SORTED enumeration of user roles

    A role defines a set of privileges the user can perform
    Roles are sorted from lower to highest privileges
    USER is the role assigned by default A user with a higher/lower role is denoted super/infra user

    ANONYMOUS : User who is not logged in. Mostly for testing purposes
    GUEST     : Temporary user with limited access. E.g. used for demos for unregistred users under-users
    USER      : Registered user. Basic permissions to use the platform [default]
    TESTER    : Upgraded user. First level of super-user with privileges to test the framework.
                Can use everything but does not have an effect in other users or actual data
    ADMIN     : Framework's administrator. Has access to everything, even other user's setup.
                Not exposed to the front-end but for internal management.

    See security_access.py
    """
    ANONYMOUS = "ANONYMOUS"
    GUEST = "GUEST"
    USER = "USER"
    TESTER = "TESTER"
    ADMIN = "ADMIN"

    @classmethod
    def super_users(cls):
        return list(itertools.takewhile(lambda e: e!=cls.USER, cls))

    # TODO: add comparison https://portingguide.readthedocs.io/en/latest/comparisons.html


#
# A role defines a set of operations that the user *can* perform
#    - Every operation is named as a resource and an action
#    - Resource is named hierarchically
#    - Roles can inherit permitted operations from other role
#
ROLES_PERMISSIONS = {
  UserRole.ANONYMOUS: { },
  UserRole.GUEST: {
      "can": [
          "studies.templates.read",
          "study.node.data.pull",
          "study.start",             # TODO: should mean study.*.start ??? bubble-up
          "study.stop",
          "study.update"
      ]
  },
  UserRole.USER: {
      "can": [
          "studies.user.read",
          "studies.user.create",
          "studies.user.edit",
          "studies.user.delete",
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
      "inherits": [UserRole.GUEST]
  },
  UserRole.TESTER: {
      "can": [
          "services.all.read",
          "preferences.role.update",
          "study.nodestree.uuid.read",
          "study.logger.debug.read"
      ],
      "inherits": [UserRole.USER, UserRole.GUEST]
  },
  UserRole.ADMIN: {
      "can": [],
      "inherits": [UserRole.TESTER, UserRole.USER, UserRole.GUEST]
  }
}


def named_permissions() -> List[str]:
    permissions = []
    for role in ROLES_PERMISSIONS:
        permissions += ROLES_PERMISSIONS[role].get("can", list())
    return permissions

def split_permission_name(permission:str) -> Tuple[str, str]:
    parts = permission.split(".")
    resource, action = ".".join(parts[:-1]), parts[-1]
    return (resource, action)
