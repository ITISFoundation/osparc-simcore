from models_library.user_preferences import PreferenceIdentifier, PreferenceName
from simcore_service_webserver.users._preferences_models import (
    TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference,
    get_preference_identifier,
    get_preference_name,
)


def test_get_preference_name_and_get_preference_identifier():
    preference_name: PreferenceName = (
        TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference.get_preference_name()
    )
    assert (
        preference_name == "TelemetryLowDiskSpaceWarningThresholdFrontendUserPreference"
    )
    preference_identifier: PreferenceIdentifier = get_preference_identifier(
        preference_name
    )
    assert preference_identifier != preference_name
    assert preference_identifier == "lowDiskSpaceThreshold"

    preference_name_via_identifier: PreferenceName = get_preference_name(
        preference_identifier
    )
    assert preference_name_via_identifier == preference_name
