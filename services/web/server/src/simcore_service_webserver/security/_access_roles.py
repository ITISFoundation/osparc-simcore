""" Defines different user roles and its associated permission

    This definition is consumed by the security._access_model to build an access model for the framework
    The access model is created upon setting up of the security subsystem
"""


from typing import TypedDict

from simcore_postgres_database.models.users import UserRole


class PermissionDict(TypedDict, total=False):
    can: list[str]
    inherits: list[UserRole]


# A role defines a set of operations that the user *can* perform
#    - Every operation is named as a resource and an action
#    - Resource is named hierarchically
#    - Roles can inherit permitted operations from other role
#
#
# NOTE:
#   - keep UI equivalents in the same line
#   - DO NOT over-granulate permissions. Add permission label ONLY to discrimitate access among roles
#     If only needed to discrimiate a resource use `resource.sub_resource.*`
#   - All services* are not necessary since it only requires login and there is no distinction among logged in users.
#

ROLES_PERMISSIONS: dict[UserRole, PermissionDict] = {
    UserRole.ANONYMOUS: PermissionDict(can=[]),
    UserRole.GUEST: PermissionDict(
        can=[
            "project.update",
            "storage.locations.*",
            "storage.files.*",
            "user.notifications.read",
            "groups.read",
            "project.open",
            "project.read",
            "project.node.read",
            "services.pipeline.*",
            "services.interactive.*",
            "services.catalog.*",
        ]
    ),
    UserRole.USER: PermissionDict(
        can=[
            "clusters.delete",
            "clusters.read",
            "clusters.write",
            "groups.*",
            "product.price.read",
            "project.access_rights.update",
            "project.classifier.*",
            "project.close",
            "project.create",
            "project.delete",
            "project.duplicate",
            "project.export",
            "project.import",
            "project.node.create",
            "project.node.delete",
            "project.node.update",
            "project.tag.*",
            "project.template.create",
            "project.wallet.*",
            "resource-usage.read",
            "tag.crud.*",
            "user.apikey.*",
            "user.notifications.update",
            "user.notifications.write",
            "user.permissions.read",
            "user.profile.update",
            "user.tokens.*",
            "wallets.*",
        ],
        inherits=[UserRole.GUEST, UserRole.ANONYMOUS],
    ),
    UserRole.TESTER: PermissionDict(
        can=[
            "clusters.create",
            "diagnostics.read",
            "project.snapshot.read",
            "project.snapshot.create",
        ],
        inherits=[UserRole.USER],
    ),
    UserRole.PRODUCT_OWNER: PermissionDict(
        can=[
            "product.details.*",
            "product.invitations",
        ],
        inherits=[UserRole.TESTER],
    ),
    UserRole.ADMIN: PermissionDict(
        can=[
            "admin.*",
            "storage.files.sync",
        ],
        inherits=[UserRole.TESTER],
    ),
}


assert set(ROLES_PERMISSIONS) == set(  # nosec
    UserRole
), "All user roles must be part define permissions"  # nosec
