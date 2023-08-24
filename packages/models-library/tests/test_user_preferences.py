# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Iterator
from typing import Any

import arrow
import pytest
from models_library.services import ServiceKey
from models_library.services_ui import WidgetType
from models_library.user_preferences import (
    BaseBackendUserPreference,
    BaseFrontendUserPreference,
    BaseUserPreferenceModel,
    BaseUserServiceUserPreference,
    PreferenceType,
    PreferenceWidgetType,
    _AutoRegisterMeta,
    get_registered_classes,
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
    assert parse_obj_as(BaseUserPreferenceModel, base_data)


def test_backend_preferences(value: Any):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.BACKEND, value=value
    )
    assert parse_obj_as(BaseBackendUserPreference, base_data)


@pytest.mark.parametrize("widget_type", PreferenceWidgetType)
def test_frontend_preferences(value: Any, widget_type: PreferenceWidgetType):
    base_data = _get_base_user_preferences_data(
        preference_type=PreferenceType.FRONTEND, value=value
    )
    base_data.update(
        {
            "widget_type": widget_type,
            "display_label": "test display label",
            "tooltip_message": "test tooltip message",
        }
    )
    assert parse_obj_as(BaseFrontendUserPreference, base_data)


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
    assert parse_obj_as(BaseUserServiceUserPreference, base_data)


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

    registered_classes = get_registered_classes()
    assert registered_classes[Pref1.__name__] == Pref1

    # usage
    pref1 = Pref1(value=value)
    assert isinstance(pref1, BaseBackendUserPreference)


@pytest.mark.parametrize("widget_type_value", PreferenceWidgetType)
def test_user_defined_frontend_preference(
    value: Any,
    widget_type_value: PreferenceWidgetType,
    unregister_defined_classes: None,
):
    # definition of a new custom property
    class Pref1(BaseFrontendUserPreference):
        widget_type: WidgetType = widget_type_value
        display_label: str = "test display label"
        tooltip_message: str = "test tooltip message"

    registered_classes = get_registered_classes()
    assert registered_classes[Pref1.__name__] == Pref1

    # usage
    pref1 = Pref1(value=value)
    assert isinstance(pref1, BaseFrontendUserPreference)


@pytest.mark.parametrize("service_key_value", _SERVICE_KEY_SAMPLES)
def test_user_defined_user_service_preference(
    value: Any, service_key_value: ServiceKey, unregister_defined_classes: None
):
    # definition of a new custom property
    class Pref1(BaseUserServiceUserPreference):
        service_key: ServiceKey = service_key_value

    registered_classes = get_registered_classes()
    assert registered_classes[Pref1.__name__] == Pref1

    # usage
    pref1 = Pref1(value=value, last_changed_utc_timestamp=_get_utc_timestamp())
    assert isinstance(pref1, BaseUserServiceUserPreference)
