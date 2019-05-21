""" Defines different user roles and its associated permission

    This definition is consumed by the security_access_model to build an access model for the framework
    The access model is created upon setting up of the security subsystem
"""
import itertools
from enum import Enum


class UserRole(Enum):
    """ SORTED enumeration of user roles

    A role defines a set of privileges the user can perform
    Roles are sorted from lower to highest privileges
    USER is the role assigned by default A user with a higher/lower role is denoted super/infra user

    ANONYMOUS : Temporary user with limited access. E.g. used for demos for unregistred users under-users
    USER      : Registered user. Basic permissions to use the platform [default]
    TESTER    : Upgraded user. First level of super-user with privileges to test the framework.
                Can use everything but does not have an effect in other users or actual data

    See security_access.py
    """
    ANONYMOUS = "ANONYMOUS"
    USER = "USER"
    TESTER = "TESTER"

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
  UserRole.ANONYMOUS: {
      "can": [
        "project.read",
      ]
  },
  UserRole.USER: {
      "can": [
          "project.create",
          "project.update",
          "project.delete",
      ],
      "inherits": [UserRole.ANONYMOUS]
  },
  UserRole.TESTER: {
      "can": [
      ],
      "inherits": [UserRole.USER]
  }
}
