from common_library.errors_classes import OsparcErrorMixin


class ServiceMetadataNotFoundError(OsparcErrorMixin, Exception):
    msg_template = "Service metadata for key {key} and version {version} not found"
