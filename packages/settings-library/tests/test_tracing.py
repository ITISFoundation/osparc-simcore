# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import pytest
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from settings_library.tracing import TracingSettings

_REQUIRED_ENVS = {
    "TRACING_OPENTELEMETRY_COLLECTOR_ENDPOINT": "http://opentelemetry-collector",
    "TRACING_OPENTELEMETRY_COLLECTOR_PORT": "4318",
    "TRACING_OPENTELEMETRY_SAMPLING_PROBABILITY": "1.0",
}


def test_traced_functions_defaults_to_empty(monkeypatch: pytest.MonkeyPatch):
    with monkeypatch.context() as patch:
        setenvs_from_dict(patch, _REQUIRED_ENVS)
        settings = TracingSettings.create_from_envs()
        assert settings.TRACING_OPENTELEMETRY_TRACED_FUNCTIONS == ""


def test_traced_functions_accepts_valid_targets(monkeypatch: pytest.MonkeyPatch):
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {
                **_REQUIRED_ENVS,
                "TRACING_OPENTELEMETRY_TRACED_FUNCTIONS": "pkg.module:function, pkg.module:Class.method",
            },
        )
        settings = TracingSettings.create_from_envs()
        assert settings.TRACING_OPENTELEMETRY_TRACED_FUNCTIONS == "pkg.module:function, pkg.module:Class.method"


@pytest.mark.parametrize(
    "invalid_value",
    [
        "no_colon_here",
        "pkg.module:",
        ":function",
        "pkg.module:1bad",
        "pkg..module:function",
    ],
)
def test_traced_functions_rejects_invalid_targets(monkeypatch: pytest.MonkeyPatch, invalid_value: str):
    with monkeypatch.context() as patch:
        setenvs_from_dict(
            patch,
            {**_REQUIRED_ENVS, "TRACING_OPENTELEMETRY_TRACED_FUNCTIONS": invalid_value},
        )
        with pytest.raises(ValidationError):
            TracingSettings.create_from_envs()
