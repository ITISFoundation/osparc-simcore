import sqlalchemy as sa
from sqlalchemy.sql import func

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
        "parent_folder",
        sa.BigInteger,
        sa.ForeignKey(
            "folders.id",
            name="fk_folders_to_folders_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.Column(
        "owner",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_folders_to_groups_gid",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
        nullable=True,
        doc="Traces back the creator of the folder",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "last_modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp with last update",
    ),
)

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
        "read",
        sa.Boolean(),
        nullable=False,
        doc="read access on folder content",
    ),
    sa.Column(
        "write",
        sa.Boolean(),
        nullable=False,
        doc="write access on folder content",
    ),
    sa.Column(
        "delete",
        sa.Boolean(),
        nullable=False,
        doc="can remove the the entry pointed by folder_id",
    ),
    sa.Column(
        "admin",
        sa.Boolean(),
        nullable=False,
        doc="can alter folder_access_rights entries except the owner's one",
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
        "project_id",
        sa.BigInteger,
        sa.ForeignKey(
            "projects.id",
            name="fk_folders_to_projects_to_projects_id",
            onupdate="CASCADE",
            ondelete="CASCADE",
        ),
    ),
    sa.PrimaryKeyConstraint("folder_id", "project_id", name="projects_to_folder_pk"),
    sa.Column(
        "created_by",
        sa.BigInteger,
        sa.ForeignKey(
            "groups.gid",
            name="fk_folders_to_groups_gid",
            ondelete="SET NULL",
        ),
        nullable=True,
        doc="Traces back the person who added the project to the folder",
    ),
    sa.Column(
        "created_at",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp auto-generated upon creation",
    ),
    sa.Column(
        "last_modified",
        sa.DateTime(),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp with last update",
    ),
)

# PROCEDURES ------------------------

update_parent_last_modified_ddl = sa.DDL(
    """
CREATE OR REPLACE FUNCTION update_parent_last_modified()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.parent_folder IS NOT NULL THEN
        UPDATE folders
        SET last_modified = NOW()
        WHERE id = NEW.parent_folder;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
)

update_folders_last_modified_ddl = sa.DDL(
    """
CREATE OR REPLACE FUNCTION update_folders_last_modified()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE folders
    SET last_modified = NOW()
    WHERE id = NEW.folder_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""
)


# TRIGGERS ------------------------

trg_update_parent_last_modified_ddl = sa.DDL(
    """
DROP TRIGGER IF EXISTS trg_update_parent_last_modified on folders;
CREATE TRIGGER trg_update_parent_last_modified
AFTER INSERT OR UPDATE ON folders
    FOR EACH ROW
    EXECUTE FUNCTION update_parent_last_modified();
"""
)

trg_update_folders_access_rights_last_modified_ddl = sa.DDL(
    """
DROP TRIGGER IF EXISTS trg_update_folders_access_rights_last_modified on folders_access_rights;
CREATE TRIGGER trg_update_folders_access_rights_last_modified
AFTER INSERT OR UPDATE OR DELETE ON folders_access_rights
    FOR EACH ROW
    EXECUTE FUNCTION update_folders_last_modified();
"""
)

trg_update_folders_to_projects_last_modified_ddl = sa.DDL(
    """
DROP TRIGGER IF EXISTS trg_update_folders_to_projects_last_modified on folders_to_projects;
CREATE TRIGGER trg_update_folders_to_projects_last_modified
AFTER INSERT OR UPDATE OR DELETE ON folders_to_projects
    FOR EACH ROW
    EXECUTE FUNCTION update_folders_last_modified();
"""
)

sa.event.listen(folders, "after_create", update_parent_last_modified_ddl)
sa.event.listen(folders, "after_create", update_folders_last_modified_ddl)
sa.event.listen(folders, "after_create", trg_update_parent_last_modified_ddl)
sa.event.listen(
    folders_access_rights,
    "after_create",
    trg_update_folders_access_rights_last_modified_ddl,
)
sa.event.listen(
    folders_to_projects,
    "after_create",
    trg_update_folders_to_projects_last_modified_ddl,
)
