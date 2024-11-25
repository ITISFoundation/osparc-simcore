from enum import Enum
from functools import total_ordering

import sqlalchemy as sa

from ._common import RefActions
from .base import metadata

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


users = sa.Table(
    "users",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger(),
        nullable=False,
        doc="Primary key index for user identifier",
    ),
    sa.Column(
        "name",
        sa.String(),
        nullable=False,
        doc="username is a unique short user friendly identifier e.g. pcrespov, sanderegg, GitHK, ...",
    ),
    sa.Column(
        "first_name",
        sa.String(),
        doc="User's first name",
    ),
    sa.Column(
        "last_name",
        sa.String(),
        doc="User's last/family name",
    ),
    sa.Column(
        "email",
        sa.String(),
        nullable=False,
        doc="Validated email",
    ),
    sa.Column(
        "phone",
        sa.String(),
        nullable=True,  # since 2FA can be configured optional
        doc="Confirmed user phone used e.g. to send a code for a two-factor-authentication."
        "NOTE: new policy (NK) is that the same phone can be reused therefore it does not has to be unique",
    ),
    sa.Column(
        "password_hash",
        sa.String(),
        nullable=False,
        doc="Hashed password",
    ),
    sa.Column(
        "primary_gid",
        sa.BigInteger(),
        sa.ForeignKey(
            "groups.gid",
            name="fk_users_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
        doc="User's group ID",
    ),
    sa.Column(
        "status",
        sa.Enum(UserStatus),
        nullable=False,
        default=UserStatus.CONFIRMATION_PENDING,
        doc="Status of the user account. SEE UserStatus",
    ),
    sa.Column(
        "role",
        sa.Enum(UserRole),
        nullable=False,
        default=UserRole.USER,
        doc="Use for role-base authorization",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
        doc="Registration timestamp",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),  # this will auto-update on modification
        doc="Last modification timestamp",
    ),
    sa.Column(
        "expires_at",
        sa.DateTime(),
        nullable=True,
        doc="Sets the expiration date for trial accounts."
        "If set to NULL then the account does not expire.",
    ),
    # ---------------------------
    sa.PrimaryKeyConstraint("id", name="user_pkey"),
    sa.UniqueConstraint("name", name="user_name_ukey"),
    sa.UniqueConstraint("email", name="user_login_key"),
)


# ------------------------ TRIGGERS

new_user_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS user_modification on users;
CREATE TRIGGER user_modification
AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE set_user_groups();
"""
)


# ---------------------- PROCEDURES
set_user_groups_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION set_user_groups() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- set primary group
        INSERT INTO "groups" ("name", "description", "type") VALUES (NEW.name, 'primary group', 'PRIMARY') RETURNING gid INTO group_id;
        INSERT INTO "user_to_groups" ("uid", "gid") VALUES (NEW.id, group_id);
        UPDATE "users" SET "primary_gid" = group_id WHERE "id" = NEW.id;
        -- set everyone group
        INSERT INTO "user_to_groups" ("uid", "gid") VALUES (NEW.id, (SELECT "gid" FROM "groups" WHERE "type" = 'EVERYONE'));
    ELSIF TG_OP = 'UPDATE' THEN
        UPDATE "groups" SET "name" = NEW.name WHERE "gid" = NEW.primary_gid;
    ELSEIF TG_OP = 'DELETE' THEN
        DELETE FROM "groups" WHERE "gid" = OLD.primary_gid;
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
"""
)

sa.event.listen(
    users,
    "after_create",
    set_user_groups_procedure,
)
sa.event.listen(
    users,
    "after_create",
    new_user_trigger,
)
