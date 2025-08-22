from ..errors import WebServerBaseError


class FoldersValueError(WebServerBaseError, ValueError): ...


class FolderValueNotPermittedError(FoldersValueError):
    msg_template = "Provided value is not permitted: {details}"


class FolderNotFoundError(FoldersValueError):
    msg_template = "Folder not found: {details}"


class FolderAccessForbiddenError(FoldersValueError):
    msg_template = "Folder access forbidden: {details}"


class FolderGroupNotFoundError(FoldersValueError):
    msg_template = "Folder group not found: {details}"


class FoldersRuntimeError(WebServerBaseError, RuntimeError): ...


class FolderNotTrashedError(FoldersRuntimeError):
    msg_template = (
        "Cannot delete folder {folder_id} since it was not trashed first: {details}"
    )


class FolderBatchDeleteError(FoldersRuntimeError):
    msg_template = "One or more folders could not be deleted: {errors}"
