from common_library.errors_classes import OsparcErrorMixin


class EfsGuardianBaseError(OsparcErrorMixin, Exception):
    """EFS guardian base error class."""
