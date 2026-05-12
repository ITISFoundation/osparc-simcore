# Errors raised by node_ports module as NodeportsException
#
#
#  NOTE: Error message SHALL explain the reason for the error and it is preferred in one line, i.e. avoid '\n' in message
#
#


class NodeportsError(Exception):
    """Basic exception for errors raised in nodeports

    Subclasses with custom __init__ parameters should define `_pickle_args`
    as a tuple of attribute names to enable proper pickling/unpickling.

    Example:
        class MyError(NodeportsError):
            _pickle_args = ("my_attr",)

            def __init__(self, my_attr):
                self.my_attr = my_attr
                super().__init__(f"Error with {my_attr}")
    """

    _pickle_args: tuple[str, ...] = ()

    def __init__(self, msg: str | None = None):
        super().__init__(msg or "An error occurred in simcore")

    def __reduce__(self):
        if self._pickle_args:
            args = tuple(getattr(self, attr) for attr in self._pickle_args)
            return (self.__class__, args)
        # Default: use self.args (the message passed to Exception)
        return (self.__class__, self.args)


class ReadOnlyError(NodeportsError):
    """Trying to modify read-only object"""

    _pickle_args = ("obj",)

    def __init__(self, obj):
        super().__init__(f"Trying to modify read-only object {obj}")
        self.obj = obj


class UnboundPortError(NodeportsError, IndexError):
    """Accessed port is not configured"""

    _pickle_args = ("port_index",)

    def __init__(self, port_index):
        super().__init__(f"No port bound at index {port_index}")
        self.port_index = port_index


class InvalidItemTypeError(NodeportsError):
    """Item type incorrect"""

    _pickle_args = ("item_type", "item_value")

    def __init__(self, item_type: str, item_value: str, msg: str | None = None):
        super().__init__(msg or f"Invalid item type, value [{item_value}] does not qualify as type [{item_type}]")
        self.item_type = item_type
        self.item_value = item_value


class InvalidProtocolError(NodeportsError):
    """Invalid protocol used"""

    _pickle_args = ("dct",)

    def __init__(self, dct, msg: str | None = None):
        super().__init__(f"Invalid protocol used: {dct} [{msg}]")
        self.dct = dct


class StorageInvalidCallError(NodeportsError):
    """Storage returned an error 400<=status<500"""


class StorageServerIssueError(NodeportsError):
    """Storage returned an error status>=500"""


class S3TransferError(NodeportsError):
    """S3 transfer error"""

    def __init__(self, msg: str | None = None):
        super().__init__(msg or "Error while transferring to/from S3 storage")


class AwsS3BadRequestRequestTimeoutError(NodeportsError):
    """Sometimes the request to S3 can time out and a 400 with a `RequestTimeout`
    reason in the body will be received. For details regarding the error
    see https://docs.aws.amazon.com/AmazonS3/latest/API/ErrorResponses.html

    In this case the entire multipart upload needs to be abandoned and retried.
    """

    _pickle_args = ("body",)

    def __init__(self, body: str):
        super().__init__(f"S3 replied with 400 RequestTimeout: {body=}")
        self.body = body


class S3InvalidPathError(NodeportsError):
    """S3 transfer error"""

    _pickle_args = ("object_name",)

    def __init__(self, s3_object_name):
        super().__init__(f"No object in S3 storage at {s3_object_name}")
        self.object_name = s3_object_name


class S3InvalidStoreError(NodeportsError):
    """S3 transfer error"""

    _pickle_args = ("store",)

    def __init__(self, s3_store):
        super().__init__(f"Invalid store used: {s3_store}")
        self.store = s3_store


class InvalidDownloadLinkError(NodeportsError):
    """Download link is invalid"""

    _pickle_args = ("link",)

    def __init__(self, link):
        super().__init__(f"Invalid link [{link}]")
        self.link = link


class TransferError(NodeportsError):
    """Download/Upload transfer error"""

    _pickle_args = ("link",)

    def __init__(self, link):
        super().__init__(f"Error while transferring to/from [{link}]")
        self.link = link


class StorageConnectionError(NodeportsError):
    """S3 transfer error"""

    _pickle_args = ("store", "additional_msg")

    def __init__(self, s3_store, additional_msg=None):
        super().__init__(f"Connection to store {s3_store} failed: {additional_msg}")
        self.store = s3_store
        self.additional_msg = additional_msg


class PortNotFoundError(NodeportsError):
    """Accessed key does not exist"""


class NodeNotFoundError(NodeportsError):
    """The given node_uuid was not found in the comp_tasks table"""

    _pickle_args = ("node_uuid", "project_id")

    def __init__(self, node_uuid: str, project_id: str):
        self.node_uuid = node_uuid
        self.project_id = project_id
        msg = (
            f"the node id {node_uuid} was not found in comp_tasks "
            f"for project_id={project_id}. This may indicate the "
            "service version is not registered in the catalog "
            "or has no valid pricing plan configured."
        )
        super().__init__(msg)


class ProjectNotFoundError(NodeportsError):
    """The given node_uuid was not found"""

    _pickle_args = ("project_id",)

    def __init__(self, project_id):
        self.project_id = project_id
        super().__init__(f"the {project_id=} was not found")


class SymlinkToSymlinkIsNotUploadableError(NodeportsError):
    """Not possible to upload a symlink to a symlink"""

    _pickle_args = ("symlink", "symlink_target_path")

    def __init__(self, symlink, symlink_target_path):
        message = (
            f"'{symlink}' is pointing to '{symlink_target_path}' which is itself a symlink. This is not supported!"
        )
        super().__init__(message)
        self.symlink = symlink
        self.symlink_target_path = symlink_target_path


class AbsoluteSymlinkIsNotUploadableError(NodeportsError):
    """absolute symlink is not uploadable"""

    _pickle_args = ("symlink", "symlink_target_path")

    def __init__(self, symlink, symlink_target_path):
        message = (
            f"Absolute symlinks are not supported: "
            f"{symlink} points to {symlink_target_path} "
            "Try with relative symlinks!"
        )
        super().__init__(message)
        self.symlink = symlink
        self.symlink_target_path = symlink_target_path
