from ._trash_service import (
    batch_delete_trashed_workspaces_as_admin,
    delete_trashed_workspace,
    list_trashed_workspaces,
)

__all__: tuple[str, ...] = (
    "delete_trashed_workspace",
    "list_trashed_workspaces",
    "batch_delete_trashed_workspaces_as_admin",
)

# nopycln: file
