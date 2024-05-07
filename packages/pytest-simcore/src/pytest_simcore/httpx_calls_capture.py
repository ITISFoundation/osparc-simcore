# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from collections.abc import Callable
from pathlib import Path

import pytest
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.httpx_client_base_dev import AsyncClientCaptureWrapper


@pytest.fixture(scope="session")
def httpx_calls_capture_path_or_none(request: pytest.FixtureRequest) -> Path | None:
    capture_path = None
    if capture_path := request.config.getoption("--httpx-calls-capture-path"):
        assert isinstance(capture_path, Path)
        assert capture_path.is_file()
    return capture_path


@pytest.fixture
def spy_async_client_or_none(
    mocker: MockerFixture, httpx_calls_capture_path_or_none: Path | None
) -> Callable[[str], MockType | None]:
    def _(module_name: str) -> MockType | None:
        if httpx_calls_capture_path_or_none is not None:
            print(
                "🚨 httpx capture enabled.",
                "Saving captures from '{module_name}' at",
                httpx_calls_capture_path_or_none,
                "...",
            )

            def _wrapper(*args, **kwargs):
                assert not args
                assert httpx_calls_capture_path_or_none
                return AsyncClientCaptureWrapper(
                    capture_file=httpx_calls_capture_path_or_none, **kwargs
                )

            spy: MockType = mocker.patch(module_name, side_effect=_wrapper)
            return spy
        return None

    return _
