"""Domain exceptions for user_preferences."""


class UserPreferencesError(Exception):
    """Base exception for user_preferences domain."""


class FrontendUserPreferenceIsNotDefinedError(UserPreferencesError):
    """Raised when a frontend user preference is not defined."""


class CouldNotCreateOrUpdateUserPreferenceError(UserPreferencesError):
    """Raised when a user preference cannot be created or updated."""
