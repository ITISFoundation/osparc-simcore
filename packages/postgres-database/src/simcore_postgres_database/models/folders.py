from typing import Final

import sqlalchemy as sa

from ._common import (
    column_created_datetime,
    column_modified_datetime,
    register_modified_datetime_auto_update_trigger,
)
from .base import metadata

folders = sa.Table(
    "folders",
    metadata,
    sa.Column(
        "id",
        sa.BigInteger,
        nullable=False,
        autoincrement=True,
        primary_key=True,
        doc="Primary key",
    ),
    sa.Column(
        "name",
        sa.String,
        nullable=False,
        doc="name of the folder",
    ),
    sa.Column(
        "description",
        sa.String,
        nullable=False,
        server_default="",
        doc="user provided description for the folder",
    ),
    sa.Column(
        "created_by",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_folders_to_groups_gid",
            ondelete="SET NULL",
        ),
        nullable=True,
        doc="traces who created the folder",
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
)


register_modified_datetime_auto_update_trigger(folders)

folders_access_rights = sa.Table(
    "folders_access_rights",
    metadata,
    sa.Column(
        "folder_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_access_rights_to_folders_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "gid",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_folders_access_rights_to_groups_gid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "traversal_parent_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_folders_id_via_traversal_parent_id",
            ondelete="SET NULL",
        ),
        doc=(
            "used for listing the contes of the folders, "
            "can be changed by the user by moving the folder"
        ),
    ),
    sa.Column(
        "original_parent_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_folders_id_via_original_parent_id",
            ondelete="SET NULL",
        ),
        doc=(
            "initially equal the same as `traversal_parent_id`, "
            "keeps track of the original parent, "
            "can never be changed once insteted"
        ),
    ),
    sa.Column(
        "read",
        sa.Boolean(),
        nullable=False,
        doc=(
            "if True can: "
            "view folders inside current folder "
            "view projects inside current folder"
        ),
    ),
    sa.Column(
        "write",
        sa.Boolean(),
        nullable=False,
        doc=(
            "if True can: "
            "create folder inside current folder, "
            "add project to folder"
        ),
    ),
    sa.Column(
        "delete",
        sa.Boolean(),
        nullable=False,
        doc=(
            "if True can: "
            "share folder, "
            "rename folder, "
            "edit folder description, "
            "delete folder, "
            "delete project form folder"
        ),
    ),
    sa.PrimaryKeyConstraint("folder_id", "gid", name="folders_access_rights_pk"),
)


folders_to_projects = sa.Table(
    "folders_to_projects",
    metadata,
    sa.Column(
        "folder_id",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_projects_to_folders_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "project_uuid",
        sa.String,
        sa.ForeignKey(
            "projects.uuid",
            name="fk_folders_to_projects_to_projects_uuid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    column_created_datetime(timezone=True),
    column_modified_datetime(timezone=True),
    sa.PrimaryKeyConstraint("folder_id", "project_uuid", name="projects_to_folder_pk"),
)

register_modified_datetime_auto_update_trigger(folders_to_projects)


_TRIGGER_NAME_UPDATE_FOLDER_MODIFIED: Final[str] = "update_folder_modified_timestamp"


def register_update_folder_modified_trigger(
    parent_table: sa.Table, child_table: sa.Table, parent_column_name: str
) -> None:
    """Registers a trigger to update the parent table's modified timestamp
    when changes occur in the child table.

    Arguments:
        parent_table -- the parent table to update the timestamp
        child_table -- the child table where changes are detected
        parent_column_name -- the column in the child table that references the parent
    """
    parent_table_name = parent_table.name
    child_table_name = child_table.name

    procedure_name = (
        f"{child_table_name}_update_{parent_table_name}_modified_timestamp()"
    )

    update_parent_modified_trigger = sa.DDL(
        f"""
    DROP TRIGGER IF EXISTS {child_table_name}_{_TRIGGER_NAME_UPDATE_FOLDER_MODIFIED} on {child_table_name};
    CREATE TRIGGER {child_table_name}_{_TRIGGER_NAME_UPDATE_FOLDER_MODIFIED}
    AFTER INSERT OR UPDATE OR DELETE ON {child_table_name}
    FOR EACH ROW EXECUTE PROCEDURE {procedure_name};
        """
    )
    update_parent_modified_procedure = sa.DDL(
        f"""
    CREATE OR REPLACE FUNCTION {procedure_name}
    RETURNS TRIGGER AS $$
    BEGIN
    UPDATE {parent_table_name}
    SET modified = current_timestamp
    WHERE id = NEW.{parent_column_name} OR id = OLD.{parent_column_name};
    RETURN NULL;
    END;
    $$ LANGUAGE plpgsql;
        """  # noqa: S608
    )

    sa.event.listen(child_table, "after_create", update_parent_modified_procedure)
    sa.event.listen(child_table, "after_create", update_parent_modified_trigger)


# Register triggers for folders and subfolders
register_update_folder_modified_trigger(folders, folders_access_rights, "folder_id")
register_update_folder_modified_trigger(folders, folders_to_projects, "folder_id")
