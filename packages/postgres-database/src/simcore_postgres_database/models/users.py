""" Users table

    - List of users in the framework
    - Users they have a role within the framework that provides
    them different access levels to it
"""
import itertools
from enum import Enum

import sqlalchemy as sa
from sqlalchemy.sql import func

from .base import metadata


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
        return list(itertools.takewhile(lambda e: e != cls.USER, cls))

    # TODO: add comparison https://portingguide.readthedocs.io/en/latest/comparisons.html


class UserStatus(Enum):
    """
        pending: user registered but not confirmed
        active: user is confirmed and can use the platform
        banned: user is not authorized
    """

    CONFIRMATION_PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BANNED = "BANNED"


users = sa.Table(
    "users",
    metadata,
    sa.Column("id", sa.BigInteger, nullable=False),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("email", sa.String, nullable=False),
    sa.Column("password_hash", sa.String, nullable=False),
    sa.Column(
        "primary_gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_users_gid_groups",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
    ),
    sa.Column(
        "status",
        sa.Enum(UserStatus),
        nullable=False,
        default=UserStatus.CONFIRMATION_PENDING,
    ),
    sa.Column("role", sa.Enum(UserRole), nullable=False, default=UserRole.USER),
    sa.Column("created_at", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
    sa.Column("created_ip", sa.String(), nullable=True),
    #
    sa.PrimaryKeyConstraint("id", name="user_pkey"),
    sa.UniqueConstraint("email", name="user_login_key"),
)

# ------------------------ TRIGGERS

new_user_trigger = sa.DDL(
    f"""
DROP TRIGGER IF EXISTS user_modification on users;
CREATE TRIGGER user_modification
AFTER INSERT OR UPDATE OR DELETE ON users
    FOR EACH ROW
    EXECUTE PROCEDURE set_user_groups();    
"""
)


# ---------------------- PROCEDURES
set_user_groups_procedure = sa.DDL(
    f"""
CREATE OR REPLACE FUNCTION set_user_groups() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        -- set primary group
        INSERT INTO "groups" ("name", "description", "type") VALUES (NEW.name, 'primary group', 'PRIMARY') RETURNING gid INTO group_id;
        INSERT INTO "user_to_groups" ("uid", "gid") VALUES (NEW.id, group_id);
        UPDATE "users" SET "primary_gid" = group_id WHERE "id" = NEW.id;
        -- set everyone goup
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

sa.event.listen(users, "after_create", set_user_groups_procedure)
sa.event.listen(
    users, "after_create", new_user_trigger,
)
