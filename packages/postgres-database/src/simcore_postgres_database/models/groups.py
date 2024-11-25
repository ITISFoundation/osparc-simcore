""" Groups table

    - List of groups in the framework
    - Groups have a ID, name and a list of users that belong to the group
"""

import enum

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql import func

from ._common import RefActions
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


groups = sa.Table(
    "groups",
    metadata,
    sa.Column(
        "gid",
        sa.BigInteger,
        nullable=False,
        primary_key=True,
        doc="Group unique IDentifier",
    ),
    sa.Column("name", sa.String, nullable=False, doc="Group label"),
    sa.Column("description", sa.String, nullable=False, doc="Short description"),
    sa.Column(
        "type",
        sa.Enum(GroupType),
        nullable=False,
        server_default="STANDARD",
        doc="Classification of the group based on GroupType enum",
    ),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Link to thumbnail image to use as logo",
    ),
    sa.Column(
        "inclusion_rules",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Maps user's column and regular expression."
        "Used to automatically assign a user to this group based on it's attributes",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),  # this will auto-update on modification
        doc="Timestamp with last update",
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
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="User unique IDentifier",
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_user_to_groups_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
        ),
        doc="Group unique IDentifier",
    ),
    sa.Column(
        "access_rights",
        JSONB,
        nullable=False,
        server_default=sa.text(
            '\'{"read": true, "write": false, "delete": false}\'::jsonb'
        ),
        doc="User's access rights to the group",
    ),
    sa.Column(
        "created",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp with last row update",
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
