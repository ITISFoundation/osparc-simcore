# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch
from service_integration.settings import AppSettings

CONTEXT_DEFAULTS: dict[str, Any] = {
    k: x.default for k, x in AppSettings.__fields__.items()
}
CONTEXT_ARGS: list[dict[str, Any]] = [
    CONTEXT_DEFAULTS,
    {"REGISTRY_NAME": "registry:5000"},
]


@pytest.fixture(params=CONTEXT_ARGS)
def env(request, monkeypatch: MonkeyPatch) -> None:
    for k, v in request.param.items():
        monkeypatch.setenv(k, v)


@pytest.mark.parametrize("context_kwargs", CONTEXT_ARGS)
def test_context_from_args(context_kwargs: dict[str, Any]) -> None:
    context = AppSettings(**context_kwargs)
    assert context


def test_context_from_env(env: None):
    context = AppSettings()
    assert context
