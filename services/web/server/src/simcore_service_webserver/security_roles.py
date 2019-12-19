""" Defines different user roles and its associated permission

    This definition is consumed by the security_access_model to build an access model for the framework
    The access model is created upon setting up of the security subsystem
"""

from simcore_postgres_database.models.users import UserRole


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
        # Anonymous users need access to the filesystem because files are being transferred
        "project.update",
        "storage.locations.*", # "storage.datcore.read"
        "storage.files.*",

        "project.open",
        "project.read",          # "studies.user.read",
                                 # "studies.templates.read"
        # NOTE: All services* are not necessary since it only requires login
        # and there is no distinction among logged in users.
        # TODO: kept temporarily as a way to denote resources
        "services.pipeline.*",   # "study.update",
                                 # "study.start",
                                 # "study.stop",
        "services.interactive.*",# "study.node.start"
        "services.catalog.*",
      ]
  },
  UserRole.USER: {
      "can": [
          "project.create",      # "studies.user.create",
          "project.close",
          "project.delete",      # "study.node.create",
                                 # "study.node.delete",
                                 # "study.node.rename",
                                 # "study.edge.create",
                                 # "study.edge.delete"

          "user.profile.update", # "preferences.user.update",
                                 # "preferences.role.update"
          "user.tokens.*",       # "preferences.token.create",
                                 # "preferences.token.delete"

        # NOTE: All services* are not necessary since it only requires login
        # and there is no distinction among logged in users.
        # TODO: kept temporarily as a way to denote resources
      ],
      "inherits": [UserRole.GUEST, UserRole.ANONYMOUS]
  },
  UserRole.TESTER: {
      "can": [
          "project.template.create",
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
#   "study.node.data.pull", , <----------???
###   "study.start",
###   "study.stop",
###   "study.update"
# ],
# "user": [
###   "studies.user.read",
###   "studies.user.create",
###   "storage.datcore.read",
###   "preferences.user.update",
###   "preferences.token.create",
###   "preferences.token.delete",
###   "study.node.create",
###   "study.node.delete",
###   "study.node.rename",
###   "study.node.start",
#   "study.node.data.push", <----------???
#   "study.node.data.delete", <----------???
#XX   "study.edge.create",
#XX   "study.edge.delete"
# ],
# "tester": [
#   "services.all.read",   <----------???
###   "preferences.role.update",
#   "study.nodestree.uuid.read", <----------???
#   "study.logger.debug.read" <----------???
# ],
# "admin": []
