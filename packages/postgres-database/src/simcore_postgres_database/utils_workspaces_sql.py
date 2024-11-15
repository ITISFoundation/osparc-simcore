from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.workspaces_access_rights import (
    workspaces_access_rights,
)
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import BOOLEAN, INTEGER
from sqlalchemy.sql import Subquery, select


def create_my_workspace_access_rights_subquery(user_id: int) -> Subquery:
    return (
        select(
            workspaces_access_rights.c.workspace_id,
            func.json_build_object(
                "read",
                func.max(workspaces_access_rights.c.read.cast(INTEGER)).cast(BOOLEAN),
                "write",
                func.max(workspaces_access_rights.c.write.cast(INTEGER)).cast(BOOLEAN),
                "delete",
                func.max(workspaces_access_rights.c.delete.cast(INTEGER)).cast(BOOLEAN),
            ).label("my_access_rights"),
        )
        .select_from(
            workspaces_access_rights.join(
                user_to_groups, user_to_groups.c.gid == workspaces_access_rights.c.gid
            )
        )
        .where(user_to_groups.c.uid == user_id)
        .group_by(workspaces_access_rights.c.workspace_id)
    ).subquery("my_workspace_access_rights_subquery")
