# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from collections.abc import Callable

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from settings_library.tracing import TracingSettings

_REQUIRED_ENVS = {
    "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://opentelemetry-collector",
    "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "4318",
    "TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY": "1.0",
    "TRACING_OPENTELEMETRY_COLLECTOR_IMAGE_VERSION": "0.0.0",
}


@pytest.fixture
def make_settings(monkeypatch: pytest.MonkeyPatch) -> Callable[..., TracingSettings]:
    setenvs_from_dict(monkeypatch, _REQUIRED_ENVS)

    def _make(**extra_envs: str) -> TracingSettings:
        setenvs_from_dict(monkeypatch, extra_envs)
        return TracingSettings.create_from_envs()

    return _make


def test_traced_functions_defaults_to_empty(make_settings: Callable[..., TracingSettings]):
    settings = make_settings()
    assert settings.TRACING_OPENTELEMETRY_TRACED_FUNCTIONS == []


def test_traced_functions_accepts_valid_targets(make_settings: Callable[..., TracingSettings]):
    settings = make_settings(
        TRACING_OPENTELEMETRY_TRACED_FUNCTIONS='["pkg.module:function", "pkg.module:Class.method"]'
    )
    assert settings.TRACING_OPENTELEMETRY_TRACED_FUNCTIONS == ["pkg.module:function", "pkg.module:Class.method"]


@pytest.mark.parametrize(
    "invalid_value",
    [
        # valid JSON but invalid target format
        '["no_colon_here"]',
        '["pkg.module:"]',
        '[":function"]',
        '["pkg.module:1bad"]',
        '["pkg..module:function"]',
    ],
)
def test_traced_functions_rejects_invalid_targets(make_settings: Callable[..., TracingSettings], invalid_value: str):
    with pytest.raises(ValidationError):
        make_settings(TRACING_OPENTELEMETRY_TRACED_FUNCTIONS=invalid_value)


def test_traced_functions_rejects_non_json(make_settings: Callable[..., TracingSettings]):
    with pytest.raises(SettingsError):
        make_settings(TRACING_OPENTELEMETRY_TRACED_FUNCTIONS="not-json")
