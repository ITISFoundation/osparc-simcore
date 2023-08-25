# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Iterator
from copy import deepcopy
from typing import Any

import arrow
import pytest
from models_library.services import ServiceKey
from models_library.services_ui import WidgetType
from models_library.user_preferences import (
    BaseBackendUserPreference,
    BaseFrontendUserPreference,
    BaseUserServiceUserPreference,
    PreferenceType,
    ValueType,
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


def test_backend_preferences(value: Any):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.BACKEND, value=value
    )
    assert parse_obj_as(BaseBackendUserPreference, base_data)


@pytest.mark.parametrize("widget_type", WidgetType)
@pytest.mark.parametrize("value_type", ValueType)
def test_frontend_preferences(
    value: Any, widget_type: WidgetType, value_type: ValueType
):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.FRONTEND, value=value
    )

    data_with_rendered_widget = deepcopy(base_data)
    data_with_rendered_widget.update(
        {
            "render_widget": True,
            "preference_identifier": "pref-name",
            "widget_type": widget_type,
            "display_label": "test display label",
            "tooltip_message": "test tooltip message",
            "value_type": value_type,
        }
    )
    # check serialization
    with_rendered_widget_instance = parse_obj_as(
        BaseFrontendUserPreference, data_with_rendered_widget
    )
    assert set(with_rendered_widget_instance.dict().keys()) == {"value"}

    data_no_rendered_widget = deepcopy(base_data)
    data_no_rendered_widget.update(
        {
            "render_widget": False,
            "preference_identifier": "pref-name",
            "widget_type": None,
            "display_label": None,
            "tooltip_message": None,
            "value_type": value_type,
        }
    )
    # check serialization
    no_rendered_widget_instance = parse_obj_as(
        BaseFrontendUserPreference, data_no_rendered_widget
    )
    assert set(no_rendered_widget_instance.dict().keys()) == {"value"}


@pytest.mark.parametrize("service_key", _SERVICE_KEY_SAMPLES)
def test_user_service_preferences(value: Any, service_key: ServiceKey):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.USER_SERVICE, value=value
    )
    base_data.update(
        {
            "service_key": service_key,
            "last_changed_utc_timestamp": _get_utc_timestamp(),
        }
    )
    instance = parse_obj_as(BaseUserServiceUserPreference, base_data)
    assert set(instance.dict().keys()) == {"service_key", "value"}


@pytest.fixture
def unregister_defined_classes() -> Iterator[None]:
    yield
    # pylint: disable=protected-access
    _AutoRegisterMeta._registered_user_preference_classes.pop(  # noqa: SLF001
        "Pref1", None
    )


def test_user_defined_backend_preference(value: Any, unregister_defined_classes: None):
    # definition of a new custom property
    class Pref1(BaseBackendUserPreference):
        ...

    # usage
    pref1 = Pref1(value=value)
    assert isinstance(pref1, BaseBackendUserPreference)

    # check bytes serialization/deserialization
    pref1_as_bytes = pref1.json().encode()
    new_instance = Pref1.parse_raw(pref1_as_bytes)
    assert new_instance == pref1


@pytest.mark.parametrize("widget_type_value", WidgetType)
def test_user_defined_frontend_preference(
    value: Any,
    widget_type_value: WidgetType,
    unregister_defined_classes: None,
):
    # definition of a new custom property
    class Pref1(BaseFrontendUserPreference):
        render_widget = True
        value_type = ValueType.STR
        preference_identifier = "pref1"
        widget_type: WidgetType = widget_type_value
        display_label = "test display label"
        tooltip_message = "test tooltip message"

    # usage
    pref1 = Pref1(value=value)
    assert isinstance(pref1, BaseFrontendUserPreference)

    # check bytes serialization/deserialization
    pref1_as_bytes = pref1.json().encode()
    new_instance = Pref1.parse_raw(pref1_as_bytes)
    assert new_instance == pref1


@pytest.mark.parametrize("service_key_value", _SERVICE_KEY_SAMPLES)
def test_user_defined_user_service_preference(
    value: Any, service_key_value: ServiceKey, unregister_defined_classes: None
):
    # definition of a new custom property
    class Pref1(BaseUserServiceUserPreference):
        service_key: ServiceKey = service_key_value

    # usage
    pref1 = Pref1(value=value, last_changed_utc_timestamp=_get_utc_timestamp())
    assert isinstance(pref1, BaseUserServiceUserPreference)

    # check bytes serialization/deserialization
    pref1_as_bytes = pref1.json().encode()
    new_instance = Pref1.parse_raw(pref1_as_bytes)
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
