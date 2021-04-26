# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest

# Some extras to overcome https://github.com/pytest-dev/pytest/issues/363


@pytest.fixture(scope="session")
def monkeypatch_session(request):
    from _pytest.monkeypatch import MonkeyPatch

    mpatch_session = MonkeyPatch()
    yield mpatch_session
    mpatch_session.undo()


@pytest.fixture(scope="module")
def monkeypatch_module(request):
    from _pytest.monkeypatch import MonkeyPatch

    mpatch_module = MonkeyPatch()
    yield mpatch_module

    mpatch_module.undo()
