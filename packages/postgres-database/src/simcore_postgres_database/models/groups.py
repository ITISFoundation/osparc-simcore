""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""

import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from .base import metadata


class GroupType(enum.Enum):
    """
        standard: standard group, e.g. any group that is not a primary group or special group such as the everyone group
        primary: primary group, e.g. the primary group is the user own defined group that typically only contain the user (same as in linux)
        everyone: the only group for all users
    """

    STANDARD = "standard"
    PRIMARY = "primary"
    EVERYONE = "everyone"


# NOTE: using func.now() insted of python datetime ensure the time is computed server side
groups = sa.Table(
    "groups",
    metadata,
    sa.Column("gid", sa.BigInteger, nullable=False, primary_key=True),
    sa.Column("name", sa.String, nullable=False),
    sa.Column("description", sa.String, nullable=False),
    sa.Column("type", sa.Enum(GroupType), nullable=False, server_default="STANDARD"),
    sa.Column("thumbnail", sa.String, nullable=True),
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
    ),
    sa.CheckConstraint("check_group_uniqueness(name, text(type)) = 0"),
)

user_to_groups = sa.Table(
    "user_to_groups",
    metadata,
    sa.Column(
        "uid",
        sa.BigInteger,
        sa.ForeignKey(
            "users.id",
            name="fk_user_to_groups_id_users",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_user_to_groups_gid_groups",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "access_rights",
        JSONB,
        nullable=False,
        server_default=sa.text(
            "'{\"read\": true, \"write\": false, \"delete\": false}'::jsonb"
        ),
    ),
    sa.Column("created", sa.DateTime(), nullable=False, server_default=func.now()),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
    sa.UniqueConstraint("uid", "gid"),
)

# TRIGGERS ------------------------

group_delete_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS group_delete_trigger on groups;
CREATE TRIGGER group_delete_trigger
BEFORE DELETE ON groups
    FOR EACH ROW
    EXECUTE PROCEDURE group_delete_procedure();
"""
)

# PROCEDURES ------------------------
set_check_uniqueness_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION check_group_uniqueness(name text, type text) RETURNS INT AS $$
BEGIN
    IF type = 'EVERYONE' AND (SELECT COUNT(*) FROM groups WHERE groups.type = 'EVERYONE') = 1 THEN
        RETURN 127;
    END IF;
    RETURN 0;
END; $$ LANGUAGE 'plpgsql';
"""
)

set_add_unique_everyone_group = sa.DDL(
    """
INSERT INTO "groups" ("name", "description", "type") VALUES ('Everyone', 'all users', 'EVERYONE') ON CONFLICT DO NOTHING;
"""
)

set_group_delete_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION group_delete_procedure() RETURNS TRIGGER AS $$
BEGIN
    IF OLD.type = 'EVERYONE' THEN
        RAISE EXCEPTION 'Everyone group cannot be deleted';
    END IF;
    RETURN OLD;
END; $$ LANGUAGE 'plpgsql';
"""
)


sa.event.listen(groups, "before_create", set_check_uniqueness_procedure, insert=True)
sa.event.listen(groups, "after_create", set_add_unique_everyone_group)
sa.event.listen(groups, "after_create", set_group_delete_procedure)
sa.event.listen(groups, "after_create", group_delete_trigger)
