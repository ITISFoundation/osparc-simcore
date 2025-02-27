from ._trash_service import (
    batch_delete_trashed_folders_as_admin,
    delete_trashed_folder,
    list_explicitly_trashed_folders,
)

__all__: tuple[str, ...] = (
    "batch_delete_trashed_folders_as_admin",
    "delete_trashed_folder",
    "list_explicitly_trashed_folders",
)

# nopycln: file
