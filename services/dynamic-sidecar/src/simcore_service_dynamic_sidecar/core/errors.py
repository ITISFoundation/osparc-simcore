from common_library.errors_classes import OsparcErrorMixin


class BaseDynamicSidecarError(OsparcErrorMixin, Exception):
    """Used as base for all exceptions"""


class VolumeNotFoundError(BaseDynamicSidecarError):
    msg_template = (
        "Expected 1 got {volume_count} volumes labels with "
        "source_label={source_label}, service_run_id={service_run_id}: Found {volume_names}"
    )


class UnexpectedDockerError(BaseDynamicSidecarError):
    msg_template = "An unexpected Docker error occurred status_code={status_code}, message={message}"
