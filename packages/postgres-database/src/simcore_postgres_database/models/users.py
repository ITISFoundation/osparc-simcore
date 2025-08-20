import sqlalchemy as sa
from common_library.users_enums import UserRole, UserStatus
from sqlalchemy.sql import expression

from ._common import RefActions
from .base import metadata

__all__: tuple[str, ...] = (
    "UserRole",
    "UserStatus",
)

users = sa.Table(
    "users",
    metadata,
    #
    # User Identifiers ------------------
    #
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
        doc="username is a unique short user friendly identifier e.g. pcrespov, sanderegg, GitHK, ..."
        "This identifier **is public**.",
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
    #
    # User Information  ------------------
    #
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
    #
    # User Account ------------------
    #
    sa.Column(
        "status",
        sa.Enum(UserStatus),
        nullable=False,
        default=UserStatus.CONFIRMATION_PENDING,
        doc="Current status of the user's account",
    ),
    sa.Column(
        "role",
        sa.Enum(UserRole),
        nullable=False,
        default=UserRole.USER,
        doc="Used for role-base authorization",
    ),
    #
    # User Privacy Rules ------------------
    #
    sa.Column(
        "privacy_hide_username",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, it hides users.name to others",
    ),
    sa.Column(
        "privacy_hide_fullname",
        sa.Boolean,
        nullable=False,
        server_default=expression.true(),
        doc="If true, it hides users.first_name, users.last_name to others",
    ),
    sa.Column(
        "privacy_hide_email",
        sa.Boolean,
        nullable=False,
        server_default=expression.false(),
        doc="If true, it hides users.email to others",
    ),
    #
    # Timestamps ---------------
    #
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
