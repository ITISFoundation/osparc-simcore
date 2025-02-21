from ..errors import WebServerBaseError


class FoldersValueError(WebServerBaseError, ValueError):
    ...


class FolderValueNotPermittedError(FoldersValueError):
    msg_template = "Provided value is not permitted. {reason}"


class FolderNotFoundError(FoldersValueError):
    msg_template = "Folder not found. {reason}"


class FolderAccessForbiddenError(FoldersValueError):
    msg_template = "Folder access forbidden. {reason}"


class FolderGroupNotFoundError(FoldersValueError):
    msg_template = "Folder group not found. {reason}"


class FoldersRuntimeError(WebServerBaseError, RuntimeError):
    ...


class FolderNotTrashedError(FoldersRuntimeError):
    msg_template = (
        "Cannot delete folder {folder_id} since it was not trashed first: {reason}"
    )


class FolderBatchDeleteError(FoldersRuntimeError):
    msg_template = "One or more folders could not be deleted: {errors}"
