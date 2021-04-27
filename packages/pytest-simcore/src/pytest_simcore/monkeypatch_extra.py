# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Iterator

import pytest
from _pytest.fixtures import FixtureRequest
from _pytest.monkeypatch import MonkeyPatch

# Some extras to overcome https://github.com/pytest-dev/pytest/issues/363


@pytest.fixture(scope="session")
def monkeypatch_session(request: FixtureRequest) -> Iterator[MonkeyPatch]:
    assert request.scope == "session"

    mpatch_session = MonkeyPatch()
    yield mpatch_session
    mpatch_session.undo()


@pytest.fixture(scope="module")
def monkeypatch_module(request: FixtureRequest) -> Iterator[MonkeyPatch]:
    assert request.scope == "module"

    mpatch_module = MonkeyPatch()
    yield mpatch_module
    mpatch_module.undo()
