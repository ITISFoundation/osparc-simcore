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
        "can": []  # Add only permissions here to handles that do not require login.
        # Anonymous user can only access
    },
    UserRole.GUEST: {
        "can": [
            # Anonymous users need access to the filesystem because files are being transferred
            "project.update",
            "storage.locations.*",  # "storage.datcore.read"
            "storage.files.*",
            "groups.read",
            "project.open",
            "project.read",  # "studies.user.read",
            # "studies.templates.read"
            "project.node.read",
            # NOTE: All services* are not necessary since it only requires login
            # and there is no distinction among logged in users.
            # TODO: kept temporarily as a way to denote resources
            "services.pipeline.*",  # "study.update",
            # "study.start",
            # "study.stop",
            "services.interactive.*",  # "study.node.start"
            "services.catalog.*",
        ]
    },
    UserRole.USER: {
        "can": [
            "clusters.delete",
            "clusters.read",
            "clusters.write",
            "project.create",  # "studies.user.create",
            "project.close",
            "project.delete",  # "study.node.create",
            "project.export",
            "project.duplicate",
            "project.import",
            "project.access_rights.update",
            # "study.node.delete",
            # "study.node.rename",
            # "study.edge.create",
            # "study.edge.delete"
            "project.node.create",
            "project.node.delete",
            "project.template.create",
            "project.classifier.*",  # "study.classifier"
            "project.tag.*",  # "study.tag"
            "user.profile.update",  # "user.user.update",
            # "user.role.update"
            "user.apikey.*",  # "user.apikey.create",
            # "user.apikey.delete"
            "user.tokens.*",  # "user.token.create",
            # "user.token.delete"
            "groups.*",
            "tag.crud.*"  # "user.tag"
            # NOTE: All services* are not necessary since it only requires login
            # and there is no distinction among logged in users.
            # TODO: kept temporarily as a way to denote resources
        ],
        "inherits": [UserRole.GUEST, UserRole.ANONYMOUS],
    },
    UserRole.TESTER: {
        "can": [
            "clusters.create",
            "diagnostics.read",
            "project.snapshot.read",
            "project.snapshot.create",
            "project.node.update",
        ],
        "inherits": [UserRole.USER],
    },
    UserRole.ADMIN: {
        "can": [
            "admin.*",
            "storage.files.sync",
        ],
        "inherits": [UserRole.TESTER],
    },
}


# static test
assert {e for e in ROLES_PERMISSIONS} == {  # nosec
    e for e in UserRole
}, "All user rols must be part define permissions"  # nosec
