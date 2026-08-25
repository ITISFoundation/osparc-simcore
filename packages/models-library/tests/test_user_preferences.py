# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Iterator
from pathlib import Path
from typing import Any, ClassVar

import pytest
from models_library.services import ServiceKey, ServiceVersion
from models_library.user_preferences import (
    FrontendUserPreference,
    InvalidValueConstraintsError,
    NoPreferenceFoundError,
    PreferenceType,
    UserServiceUserPreference,
    _AutoRegisterMeta,
    _BaseUserPreferenceModel,
)
from pydantic import TypeAdapter, ValidationError

_SERVICE_KEY_AND_VERSION_SAMPLES: list[tuple[ServiceKey, ServiceVersion]] = [
    (
        TypeAdapter(ServiceKey).validate_python("simcore/services/comp/something-1231"),
        TypeAdapter(ServiceVersion).validate_python("0.0.1"),
    ),
    (
        TypeAdapter(ServiceKey).validate_python("simcore/services/dynamic/something-1231"),
        TypeAdapter(ServiceVersion).validate_python("0.0.1"),
    ),
    (
        TypeAdapter(ServiceKey).validate_python("simcore/services/frontend/something-1231"),
        TypeAdapter(ServiceVersion).validate_python("0.0.1"),
    ),
]


@pytest.fixture(params=[None, 1, 1.0, "str", {"a": "dict"}, ["a", "list"]])
def value(request: pytest.FixtureRequest) -> Any:
    return request.param


@pytest.fixture
def mock_file_path() -> Path:
    return Path("/a/file/path")


def _get_base_user_preferences_data(preference_type: PreferenceType, value: Any) -> dict[str, Any]:
    return {"preference_type": preference_type, "value": value}


@pytest.mark.parametrize("preference_type", PreferenceType)
def test_base_user_preference_model(value: Any, preference_type: PreferenceType):
    base_data = _get_base_user_preferences_data(preference_type=preference_type, value=value)
    assert TypeAdapter(_BaseUserPreferenceModel).validate_python(base_data)


def test_frontend_preferences(value: Any):
    base_data = _get_base_user_preferences_data(preference_type=PreferenceType.FRONTEND, value=value)

    base_data.update({"preference_identifier": "pref-name"})
    # check serialization
    frontend_preference = TypeAdapter(FrontendUserPreference).validate_python(base_data)
    assert set(frontend_preference.to_db().keys()) == {"value"}


def test_user_service_preferences(value: Any, mock_file_path: Path):
    base_data = _get_base_user_preferences_data(preference_type=PreferenceType.USER_SERVICE, value=value)
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
def restore_preference_classes_registry() -> Iterator[None]:
    # pylint: disable=protected-access
    registry = _AutoRegisterMeta.registered_user_preference_classes
    snapshot = dict(registry)
    yield
    registry.clear()
    registry.update(snapshot)


def test__frontend__user_preference(value: Any, restore_preference_classes_registry: None):
    pref1 = FrontendUserPreference.model_validate({"preference_identifier": "pref_id", "value": value})
    assert isinstance(pref1, FrontendUserPreference)


@pytest.mark.parametrize("service_key, service_version", _SERVICE_KEY_AND_VERSION_SAMPLES)
def test__user_service__user_preference(
    value: Any,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    mock_file_path: Path,
    restore_preference_classes_registry: None,
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


def test_redefine_class_with_same_name_is_not_allowed(restore_preference_classes_registry: None):
    # pylint: disable=unused-variable
    def def_class_1():
        class APreference(_BaseUserPreferenceModel): ...

    def def_class_2():
        class APreference(_BaseUserPreferenceModel): ...

    def_class_1()
    with pytest.raises(TypeError, match="was already defined"):
        def_class_2()


def test_get_preference_class_from_name_not_found():
    with pytest.raises(NoPreferenceFoundError, match="No preference class found"):
        _BaseUserPreferenceModel.get_preference_class_from_name("__missing_preference_name__")


@pytest.fixture
def capped_preference_class(restore_preference_classes_registry: None) -> type[FrontendUserPreference]:
    class CappedPreference(FrontendUserPreference):
        preference_identifier: str = "capped"
        value: int = 1800
        value_constraints: ClassVar[dict[str, Any]] = {"le": 10800}

    return CappedPreference


@pytest.mark.parametrize(
    "value, overrides, is_valid",
    [
        pytest.param(1800, None, True, id="within_class_constraint"),
        pytest.param(10800, None, True, id="at_class_constraint"),
        pytest.param(14400, None, False, id="above_class_constraint"),
        pytest.param(21600, {"le": 21600}, True, id="override_relaxes_class_constraint"),
        pytest.param(25200, {"le": 21600}, False, id="above_relaxed_override"),
        pytest.param(10800, {"le": 7200}, False, id="override_tightens_class_constraint"),
        pytest.param(30, {"ge": 60}, False, id="override_adds_constraint"),
        pytest.param("not-an-int", None, False, id="wrong_type"),
    ],
)
def test_validate_value_with_constraint_overrides(
    capped_preference_class: type[FrontendUserPreference],
    value: Any,
    overrides: dict[str, Any] | None,
    is_valid: bool,
):
    if is_valid:
        capped_preference_class.validate_value(value, overrides)
    else:
        with pytest.raises(ValidationError):
            capped_preference_class.validate_value(value, overrides)


def test_validate_value_leaves_preference_class_untouched(
    capped_preference_class: type[FrontendUserPreference],
):
    capped_preference_class.validate_value(21600, {"le": 21600})

    assert capped_preference_class.model_fields["value"].metadata == []
    assert capped_preference_class.get_default_value() == 1800
    # a value the deployment allowed must remain readable
    assert capped_preference_class.model_validate({"value": 21600}).value == 21600


def test_build_value_validator_is_cached(
    capped_preference_class: type[FrontendUserPreference],
):
    assert capped_preference_class.build_value_validator(
        {"le": 21600}
    ) is capped_preference_class.build_value_validator({"le": 21600})
    assert capped_preference_class.build_value_validator({"le": 21600}) is not (
        capped_preference_class.build_value_validator({"le": 7200})
    )


def test_unsupported_constraint_is_rejected(
    capped_preference_class: type[FrontendUserPreference],
):
    with pytest.raises(InvalidValueConstraintsError, match="unsupported"):
        capped_preference_class.validate_value(1800, {"allow_inf_nan": True})


def test_constraint_not_applicable_to_field_type_is_rejected(restore_preference_classes_registry: None):
    class Pref1(FrontendUserPreference):
        preference_identifier: str = "pref1"
        value: str = "a-value"

    with pytest.raises(InvalidValueConstraintsError, match="Unable to apply constraint"):
        Pref1.validate_value("a-value", {"ge": 1})


def test_class_constraints_are_validated_at_class_creation(restore_preference_classes_registry: None):
    with pytest.raises(InvalidValueConstraintsError, match="unsupported"):

        class Pref1(FrontendUserPreference):  # pylint: disable=unused-variable
            preference_identifier: str = "pref1"
            value: int = 1
            value_constraints: ClassVar[dict[str, Any]] = {"not_a_constraint": 1}


def test_nullable_value_accepts_none_with_constraints(restore_preference_classes_registry: None):
    class Pref1(FrontendUserPreference):
        preference_identifier: str = "pref1"
        value: int | None = None

    Pref1.validate_value(None, {"ge": 1})
    Pref1.validate_value(5, {"ge": 1})
    with pytest.raises(ValidationError):
        Pref1.validate_value(0, {"ge": 1})
