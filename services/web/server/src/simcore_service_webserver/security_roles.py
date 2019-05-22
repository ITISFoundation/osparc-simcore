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

    ANONYMOUS : The user is not logged in
    GUEST     : Temporary user with very limited access. Main used for demos and for a limited amount of time
    USER      : Registered user. Basic permissions to use the platform [default]
    TESTER    : Upgraded user. First level of super-user with privileges to test the framework.
                Can use everything but does not have an effect in other users or actual data

    See security_access.py
    """
    ANONYMOUS = "ANONYMOUS"
    GUEST = "GUEST"
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
#
# NOTE: keep UI equivalents in the same line
# NOTE: DO NOT over-granulate permissions. Add permission label ONLY to discrimitate access among roles
#       If only needed to discrimiate a resource use `resource.sub_resource.*`
#
ROLES_PERMISSIONS = {
  UserRole.ANONYMOUS: {
      "can": [] # Add only permissions here to handles that do not require login.
                # Anonymous user can only access
  },
  UserRole.GUEST: {
      "can": [
        "project.read",          # "studies.user.read", "studies.templates.read"
      ]
  },
  UserRole.USER: {
      "can": [
          "project.create",      # "studies.user.create",
          "project.update",
          "project.delete",
          "user.profile.update", # "preferences.user.update", "preferences.role.update"
          "user.tokens.*",       # "preferences.token.create", # "preferences.token.delete"
          "storage.locations.*", # "storage.datcore.read"
          "storage.files.*",
      ],
      "inherits": [UserRole.GUEST, UserRole.ANONYMOUS]
  },
  UserRole.TESTER: {
      "can": [
      ],
      "inherits": [UserRole.USER]
  }
}

#
# REFERENCE IN THE FRONT_END
#

# "anonymous": [],
# "guest": [
###   "studies.templates.read",
#   "study.node.data.pull",
#   "study.start",
#   "study.stop",
#   "study.update"
# ],
# "user": [
###   "studies.user.read",
###   "studies.user.create",
#   "storage.datcore.read",
###   "preferences.user.update",
###   "preferences.token.create",
###   "preferences.token.delete",
#   "study.node.create",
#   "study.node.delete",
#   "study.node.rename",
#   "study.node.start",
#   "study.node.data.push",
#   "study.node.data.delete",
#XX   "study.edge.create",
#XX   "study.edge.delete"
# ],
# "tester": [
#   "services.all.read",
###   "preferences.role.update",
#   "study.nodestree.uuid.read",
#   "study.logger.debug.read"
# ],
# "admin": []
