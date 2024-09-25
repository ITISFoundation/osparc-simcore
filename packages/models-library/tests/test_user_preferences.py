# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from models_library.services import ServiceKey, ServiceVersion
from models_library.user_preferences import (
    FrontendUserPreference,
    NoPreferenceFoundError,
    PreferenceType,
    UserServiceUserPreference,
    _AutoRegisterMeta,
    _BaseUserPreferenceModel,
)
from pydantic import TypeAdapter

_SERVICE_KEY_AND_VERSION_SAMPLES: list[tuple[ServiceKey, ServiceVersion]] = [
    (
        TypeAdapter(ServiceKey).validate_python("simcore/services/comp/something-1231"),
        TypeAdapter(ServiceVersion).validate_python("0.0.1"),
    ),
    (
        TypeAdapter(ServiceKey).validate_python(
            "simcore/services/dynamic/something-1231"
        ),
        TypeAdapter(ServiceVersion).validate_python("0.0.1"),
    ),
    (
        TypeAdapter(ServiceKey).validate_python(
            "simcore/services/frontend/something-1231"
        ),
        TypeAdapter(ServiceVersion).validate_python("0.0.1"),
    ),
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


@pytest.mark.parametrize("preference_type", PreferenceType)
def test_base_user_preference_model(value: Any, preference_type: PreferenceType):
    base_data = _get_base_user_preferences_data(
        preference_type=preference_type, value=value
    )
    assert TypeAdapter(_BaseUserPreferenceModel).validate_python(base_data)


def test_frontend_preferences(value: Any):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.FRONTEND, value=value
    )

    base_data.update({"preference_identifier": "pref-name"})
    # check serialization
    frontend_preference = TypeAdapter(FrontendUserPreference).validate_python(base_data)
    assert set(frontend_preference.to_db().keys()) == {"value"}


def test_user_service_preferences(value: Any, mock_file_path: Path):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.USER_SERVICE, value=value
    )
    service_key, service_version = _SERVICE_KEY_AND_VERSION_SAMPLES[0]
    base_data.update(
        {
            "service_key": service_key,
            "service_version": service_version,
            "file_path": mock_file_path,
        }
    )
    instance = TypeAdapter(UserServiceUserPreference).validate_python(base_data)
    assert set(instance.to_db().keys()) == {
        "value",
        "service_key",
        "service_version",
    }


@pytest.fixture
def unregister_defined_classes() -> Iterator[None]:
    yield
    # pylint: disable=protected-access
    _AutoRegisterMeta.registered_user_preference_classes.pop("Pref1", None)


def test__frontend__user_preference(value: Any, unregister_defined_classes: None):
    pref1 = FrontendUserPreference.model_validate(
        {"preference_identifier": "pref_id", "value": value}
    )
    assert isinstance(pref1, FrontendUserPreference)


@pytest.mark.parametrize(
    "service_key, service_version", _SERVICE_KEY_AND_VERSION_SAMPLES
)
def test__user_service__user_preference(
    value: Any,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    mock_file_path: Path,
    unregister_defined_classes: None,
):
    pref1 = UserServiceUserPreference.model_validate(
        {
            "value": value,
            "service_key": service_key,
            "service_version": service_version,
        }
    )
    assert isinstance(pref1, UserServiceUserPreference)

    # NOTE: these will be stored as bytes,
    # check bytes serialization/deserialization
    pref1_as_bytes = pref1.model_dump_json().encode()
    new_instance = UserServiceUserPreference.model_validate_json(pref1_as_bytes)
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


def test_get_preference_class_from_name_not_found():
    with pytest.raises(NoPreferenceFoundError, match="No preference class found"):
        _BaseUserPreferenceModel.get_preference_class_from_name(
            "__missing_preference_name__"
        )
