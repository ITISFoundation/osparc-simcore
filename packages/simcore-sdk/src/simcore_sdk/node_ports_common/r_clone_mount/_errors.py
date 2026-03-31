from common_library.errors_classes import OsparcErrorMixin


class _BaseRcloneMountError(OsparcErrorMixin, RuntimeError):
    pass


class WaitingForTransfersToCompleteError(_BaseRcloneMountError):
    msg_template: str = "Waiting for all transfers to complete"


class RefreshMountError(_BaseRcloneMountError):
    msg_template: str = "Failed to refresh the mount, rclone response: result={result}"


class WaitingForQueueToBeEmptyError(_BaseRcloneMountError):
    msg_template: str = "Waiting for VFS queue to be empty: queue={queue}"


class MountAlreadyStartedError(_BaseRcloneMountError):
    msg_template: str = "Mount already started for local path='{local_mount_path}'"


class NoMountFoundForRemotePathError(_BaseRcloneMountError):
    msg_template: str = "Could not find tracked mount for remote path '{remote_path}'"
