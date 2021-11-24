from typing import Dict, Any, List

import pytest
from _pytest.monkeypatch import MonkeyPatch

from service_integration.context import IntegrationContext

CONTEXT_DEFAULTS: Dict[str, Any] = {
    k: x.default for k, x in IntegrationContext.__fields__.items()
}
CONTEXT_ARGS: List[Dict[str, Any]] = [
    CONTEXT_DEFAULTS,
    {"REGISTRY_NAME": "registry:5000"},
]


@pytest.fixture(params=CONTEXT_ARGS)
def env(request, monkeypatch: MonkeyPatch) -> None:
    for k, v in request.param.items():
        monkeypatch.setenv(k, v)


@pytest.mark.parametrize("context_kwargs", CONTEXT_ARGS)
def test_context_from_args(context_kwargs: Dict[str, Any]) -> None:
    context = IntegrationContext(**context_kwargs)
    assert context


def test_context_from_env(env: None):
    context = IntegrationContext()
    assert context
