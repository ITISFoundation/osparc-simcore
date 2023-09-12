from simcore_service_webserver.users._preferences_models import (
    get_preference_identifier_to_preference_name_map,
)


def test_get_preference_identifier_to_preference_name_map():
    assert get_preference_identifier_to_preference_name_map()
