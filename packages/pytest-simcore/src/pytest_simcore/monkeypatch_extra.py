# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import warnings
from typing import Iterator

import pytest
from pytest import FixtureRequest, MonkeyPatch

warnings.warn(
    f"{__name__} is deprecated, we highly recommend to use pytest.monkeypatch at function-scope level."
    "Large scopes lead to complex problems during tests",
    DeprecationWarning,
)
# Some extras to overcome https://github.com/pytest-dev/pytest/issues/363
# SEE https://github.com/pytest-dev/pytest/issues/363#issuecomment-289830794


@pytest.fixture(scope="module")
def monkeypatch_module(request: FixtureRequest) -> Iterator[MonkeyPatch]:
    assert request.scope == "module"

    mpatch_module = MonkeyPatch()
    yield mpatch_module
    mpatch_module.undo()
