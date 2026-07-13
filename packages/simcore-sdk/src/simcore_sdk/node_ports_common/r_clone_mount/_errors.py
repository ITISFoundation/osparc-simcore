from common_library.errors_classes import OsparcErrorMixin


class _BaseRcloneMountError(OsparcErrorMixin, RuntimeError):
    pass


class WaitingForTransfersToCompleteError(_BaseRcloneMountError):
    msg_template: str = "Waiting for all transfers to complete"


class RefreshMountError(_BaseRcloneMountError):
    msg_template: str = "Failed to refresh the mount, rclone response: result={result}"


class WaitingForQueueToBeEmptyError(_BaseRcloneMountError):
    msg_template: str = "Waiting for VFS queue to be empty: queue={queue}"


class NoMountFoundForRemotePathError(_BaseRcloneMountError):
    msg_template: str = "Could not find tracked mount for remote path '{remote_path}'"


class InvalidRemotePathError(_BaseRcloneMountError):
    msg_template: str = "Invalid remote_path '{remote_path}'. Expected '{{project_id}}/{{node_id}}/DIRECTORY_PATH'"


class PortNotAssignedError(_BaseRcloneMountError):
    msg_template: str = "Container '{container_name}' has no published port for {target_port}. Ports={ports}"
