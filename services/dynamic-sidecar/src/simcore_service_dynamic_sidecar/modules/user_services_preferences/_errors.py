from common_library.errors_classes import OsparcErrorMixin


class BaseServicesPreferencesError(OsparcErrorMixin, Exception):
    ...


class DestinationIsNotADirectoryError(BaseServicesPreferencesError):
    msg_template = "Provided destination_to={destination_to} must be a directory"


class PreferencesAreTooBigError(BaseServicesPreferencesError):
    msg_template = "Preferences amount to a size of size={size} bytes. Allowed limit={limit} bytes."
