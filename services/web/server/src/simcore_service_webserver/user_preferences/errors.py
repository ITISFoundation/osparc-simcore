"""Domain exceptions for user_preferences."""

from common_library.user_messages import user_message

from ..errors import WebServerBaseError


class UserPreferencesError(WebServerBaseError, ValueError): ...


class FrontendUserPreferenceIsNotDefinedError(UserPreferencesError):
    msg_template = user_message(
        "The setting '{frontend_preference_identifier}' was not found. Please verify the setting name and try again.",
        _version=1,
    )


class FrontendUserPreferenceValueIsInvalidError(UserPreferencesError):
    msg_template = user_message(
        "The value {value} is outside the acceptable range for "
        "'{frontend_preference_identifier}'. Please enter a valid value.",
        _version=1,
    )
