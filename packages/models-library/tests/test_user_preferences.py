# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from typing import Any

import arrow
import pytest
from models_library.services import ServiceKey
from models_library.user_preferences import (
    FrontendUserPreference,
    PreferenceType,
    UserServiceUserPreference,
    _AutoRegisterMeta,
    _BaseUserPreferenceModel,
)
from pydantic import parse_obj_as

_SERVICE_KEY_SAMPLES: list[str] = [
    "simcore/services/comp/something-1231",
    "simcore/services/dynamic/something-1231",
    "simcore/services/frontend/something-1231",
]


@pytest.fixture(params=[None, 1, 1.0, "str", {"a": "dict"}, ["a", "list"]])
def value(request: pytest.FixtureRequest) -> Any:
    return request.param


@pytest.fixture
def mock_file_path() -> Path:
    return Path("/a/file/path")


def _get_base_user_preferences_data(
    preference_type: PreferenceType, value: Any
) -> dict[str, Any]:
    return {"preference_type": preference_type, "value": value}


def _get_utc_timestamp() -> float:
    return arrow.utcnow().datetime.timestamp()


@pytest.mark.parametrize("preference_type", PreferenceType)
def test_base_user_preference_model(value: Any, preference_type: PreferenceType):
    base_data = _get_base_user_preferences_data(
        preference_type=preference_type, value=value
    )
    assert parse_obj_as(_BaseUserPreferenceModel, base_data)


def test_frontend_preferences(value: Any):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.FRONTEND, value=value
    )

    data_with_rendered_widget = deepcopy(base_data)
    data_with_rendered_widget.update(
        {
            "preference_identifier": "pref-name",
        }
    )
    # check serialization
    frontend_preference = parse_obj_as(
        FrontendUserPreference, data_with_rendered_widget
    )
    assert set(frontend_preference.dict().keys()) == {"value"}


def test_user_service_preferences(value: Any, mock_file_path: Path):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.USER_SERVICE, value=value
    )
    base_data.update(
        {"service_key": _SERVICE_KEY_SAMPLES[0], "file_path": mock_file_path}
    )
    instance = parse_obj_as(UserServiceUserPreference, base_data)
    assert set(instance.dict().keys()) == {"file_path", "value"}


@pytest.fixture
def unregister_defined_classes() -> Iterator[None]:
    yield
    # pylint: disable=protected-access
    _AutoRegisterMeta._registered_user_preference_classes.pop(  # noqa: SLF001
        "Pref1", None
    )


def test__frontend__user_preference(value: Any, unregister_defined_classes: None):
    pref1 = FrontendUserPreference.parse_obj(
        {"preference_identifier": "pref_id", "value": value}
    )
    assert isinstance(pref1, FrontendUserPreference)


@pytest.mark.parametrize("service_key_value", _SERVICE_KEY_SAMPLES)
def test__user_service__user_preference(
    value: Any,
    service_key_value: ServiceKey,
    mock_file_path: Path,
    unregister_defined_classes: None,
):
    pref1 = UserServiceUserPreference.parse_obj(
        {"value": value, "service_key": service_key_value, "file_path": mock_file_path}
    )
    assert isinstance(pref1, UserServiceUserPreference)

    # NOTE: these will be stored as bytes,
    # check bytes serialization/deserialization
    pref1_as_bytes = pref1.json().encode()
    new_instance = UserServiceUserPreference.parse_raw(pref1_as_bytes)
    assert new_instance == pref1


def test_redefine_class_with_same_name_is_not_allowed(unregister_defined_classes: None):
    # pylint: disable=unused-variable
    def def_class_1():
        class APreference(_BaseUserPreferenceModel):
            ...

    def def_class_2():
        class APreference(_BaseUserPreferenceModel):
            ...

    def_class_1()
    with pytest.raises(TypeError, match="was already defined"):
        def_class_2()
