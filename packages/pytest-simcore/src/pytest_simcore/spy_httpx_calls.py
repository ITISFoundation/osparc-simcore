# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
import respx
from pydantic import parse_obj_as
from pytest_mock import MockerFixture, MockType
from pytest_simcore.helpers.httpx_client_base_dev import AsyncClientCaptureWrapper

from .helpers.httpx_calls_capture_model import (
    CreateRespxMockCallback,
    HttpApiCallCaptureModel,
    PathDescription,
    SideEffectCallback,
)


def pytest_addoption(parser: pytest.Parser):
    simcore_group = parser.getgroup("simcore")
    simcore_group.addoption(
        "--spy-httpx-calls-enabled",
        action="store",
        type=bool,
        default=None,
        help="If set, it activates a capture mechanism while the tests is running that can be used to generate mock data in respx",
    )
    simcore_group.addoption(
        "--spy-httpx-calls-capture-path",
        action="store",
        type=Path,
        default=None,
        help="Path to store capture calls from httpx clients during the tests.",
    )


@pytest.fixture(scope="session")
def httpx_calls_capture_path_or_none(request: pytest.FixtureRequest) -> Path | None:
    capture_path = None
    if capture_path := request.config.getoption("--httpx-calls-capture-path"):
        assert isinstance(capture_path, Path)
        assert capture_path.is_file()
    return capture_path


@pytest.fixture(scope="session")
def spy_httpx_calls_enabled(httpx_calls_capture_path_or_none: Path | None) -> bool:
    return httpx_calls_capture_path_or_none is not None


@pytest.fixture
def create_httpx_async_client_spy_if_enabled(
    mocker: MockerFixture, httpx_calls_capture_path_or_none: Path | None
) -> Callable[[str], MockType | None]:
    def _(module_name: str) -> MockType | None:
        if httpx_calls_capture_path_or_none is not None:
            print(
                "🚨 Spying httpx calls enabled.",
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
            spy.httpx_calls_capture_path = httpx_calls_capture_path_or_none

            return spy
        return None

    return _


class _CaptureSideEffect:
    def __init__(
        self,
        capture: HttpApiCallCaptureModel,
        side_effect: SideEffectCallback | None,
    ):
        self._capture = capture
        self._side_effect_callback = side_effect

    def __call__(self, request: httpx.Request, **kwargs) -> httpx.Response:
        capture = self._capture
        assert isinstance(capture.path, PathDescription)
        status_code: int = capture.status_code
        response_body: dict[str, Any] | list | None = capture.response_body
        assert {param.name for param in capture.path.path_parameters} == set(
            kwargs.keys()
        )
        if self._side_effect_callback:
            response_body = self._side_effect_callback(request, kwargs, capture)
        return httpx.Response(status_code=status_code, json=response_body)


@pytest.fixture
@respx.mock(assert_all_mocked=False)
def create_respx_mock_from_capture() -> CreateRespxMockCallback:
    # NOTE: multiple improvements in
    def _create_mock(
        respx_mocks: list[respx.MockRouter],
        capture_path: Path,
        side_effects_callbacks: list[SideEffectCallback],
    ) -> list[respx.MockRouter]:
        assert capture_path.is_file()
        assert capture_path.suffix == ".json"

        captures: list[HttpApiCallCaptureModel] = parse_obj_as(
            list[HttpApiCallCaptureModel], json.loads(capture_path.read_text())
        )

        if len(side_effects_callbacks) > 0:
            assert len(side_effects_callbacks) == len(captures)

        assert isinstance(respx_mocks, list)
        for router in respx_mocks:
            assert (
                router._bases
            ), "the base_url must be set before the fixture is extended"

        def _get_correct_mock_router_for_capture(
            respx_mock: list[respx.MockRouter], capture: HttpApiCallCaptureModel
        ) -> respx.MockRouter:
            for router in respx_mock:
                if capture.host == router._bases["host"].value:
                    return router
            msg = f"Missing respx.MockRouter for capture with {capture.host}"
            raise RuntimeError(msg)

        side_effects: list[_CaptureSideEffect] = []
        for ii, capture in enumerate(captures):
            url_path: PathDescription | str = capture.path
            assert isinstance(url_path, PathDescription)

            # path
            path_regex: str = str(url_path.path)
            for param in url_path.path_parameters:
                path_regex = path_regex.replace(
                    "{" + param.name + "}", param.respx_lookup
                )

            # response
            side_effect = _CaptureSideEffect(
                capture=capture,
                side_effect=side_effects_callbacks[ii]
                if len(side_effects_callbacks)
                else None,
            )

            router = _get_correct_mock_router_for_capture(respx_mocks, capture)
            r = router.request(
                capture.method.upper(),
                url=None,
                path__regex=f"^{path_regex}$",
            ).mock(side_effect=side_effect)

            assert r.side_effect == side_effect
            side_effects.append(side_effect)

        return respx_mocks

    return _create_mock
