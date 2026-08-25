"""Domain exceptions for user_preferences."""

from ..errors import WebServerBaseError


class UserPreferencesError(WebServerBaseError, ValueError): ...


class FrontendUserPreferenceIsNotDefinedError(UserPreferencesError):
    msg_template = "Frontend user preference '{frontend_preference_identifier}' is not defined"


class FrontendUserPreferenceValueIsInvalidError(UserPreferencesError):
    msg_template = "Value {value} is not allowed for frontend user preference '{frontend_preference_identifier}'"


class CouldNotCreateOrUpdateUserPreferenceError(UserPreferencesError):
    msg_template = "Could not create or update user preference"
