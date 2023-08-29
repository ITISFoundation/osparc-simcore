from simcore_service_webserver.users._preferences_models import (
    get_preference_name_to_class_name_map,
)


def test_get_preference_name_to_class_name_map():
    assert get_preference_name_to_class_name_map()
