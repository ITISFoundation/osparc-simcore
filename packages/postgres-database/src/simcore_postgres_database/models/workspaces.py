import sqlalchemy as sa

from ._common import (
    RefActions,
    column_created_datetime,
    column_modified_datetime,
    column_trashed_by_user,
    column_trashed_datetime,
)
from .base import metadata
from .users import users

workspaces = sa.Table(
    "workspaces",
    metadata,
    sa.Column(
        "workspace_id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Workspace index",
    ),
    sa.Column("name", sa.String, nullable=False, doc="Display name"),
    sa.Column("description", sa.String, nullable=True, doc="Short description"),
    sa.Column(
        "thumbnail",
        sa.String,
        nullable=True,
        doc="Link to image as to workspace thumbnail",
    ),
    sa.Column(
        "owner_primary_gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_workspaces_gid_groups",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.RESTRICT,
        ),
        nullable=False,
        doc="Identifier of the group that owns this workspace (Should be just PRIMARY GROUP)",
    ),
    sa.Column(
        "product_name",
        sa.String,
        sa.ForeignKey(
            "products.name",
            onupdate=RefActions.CASCADE,
            ondelete=RefActions.CASCADE,
            name="fk_workspaces_product_name",
        ),
        nullable=False,
        doc="Products unique name",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    column_trashed_datetime("workspace"),
    column_trashed_by_user("workspace", users_table=users),
)


# ------------------------ TRIGGERS
new_workspace_trigger = sa.DDL(
    """
DROP TRIGGER IF EXISTS workspace_modification on workspaces;
CREATE TRIGGER workspace_modification
AFTER INSERT ON workspaces
    FOR EACH ROW
    EXECUTE PROCEDURE set_workspace_to_owner_group();
"""
)


# --------------------------- PROCEDURES
assign_workspace_access_rights_to_owner_group_procedure = sa.DDL(
    """
CREATE OR REPLACE FUNCTION set_workspace_to_owner_group() RETURNS TRIGGER AS $$
DECLARE
    group_id BIGINT;
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO "workspaces_access_rights" ("gid", "workspace_id", "read", "write", "delete") VALUES (NEW.owner_primary_gid, NEW.workspace_id, TRUE, TRUE, TRUE);
    END IF;
    RETURN NULL;
END; $$ LANGUAGE 'plpgsql';
    """
)

sa.event.listen(
    workspaces, "after_create", assign_workspace_access_rights_to_owner_group_procedure
)
sa.event.listen(
    workspaces,
    "after_create",
    new_workspace_trigger,
)
