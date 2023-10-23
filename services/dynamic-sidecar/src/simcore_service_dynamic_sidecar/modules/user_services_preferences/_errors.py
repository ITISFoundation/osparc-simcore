from pydantic.errors import PydanticErrorMixin


class BaseServicesPreferencesError(PydanticErrorMixin, Exception):
    code = "dynamic_sidecar.user_service_preferences"


class DestinationIsNotADirectoryError(BaseServicesPreferencesError):
    msg_template = "Provided destination_to={destination_to} must be a directory"


class PreferencesAreTooBigError(BaseServicesPreferencesError):
    msg_template = "Preferences amount to a size of size={size} bytes. Allowed limit={limit} bytes."
