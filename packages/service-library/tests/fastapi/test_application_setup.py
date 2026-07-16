import pytest
from fastapi import FastAPI
from servicelib.fastapi.application_setup import (
    SetupAlreadyFailedError,
    ensure_single_setup,
)


def test_ensure_single_setup_runs_once():
    calls: list[FastAPI] = []

    @ensure_single_setup
    def setup_func(app: FastAPI) -> None:
        calls.append(app)

    app = FastAPI()
    setup_func(app)
    setup_func(app)
    setup_func(app)

    assert calls == [app]


def test_ensure_single_setup_is_independent_per_app_instance():
    calls: list[FastAPI] = []

    @ensure_single_setup
    def setup_func(app: FastAPI) -> None:
        calls.append(app)

    app_1 = FastAPI()
    app_2 = FastAPI()

    setup_func(app_1)
    setup_func(app_2)

    assert calls == [app_1, app_2]


def test_ensure_single_setup_passes_arguments():
    received: list[tuple[str, int]] = []

    @ensure_single_setup
    def setup_func(app: FastAPI, vtag: str, *, retries: int = 0) -> None:
        received.append((vtag, retries))

    setup_func(FastAPI(), "v0", retries=3)

    assert received == [("v0", 3)]


def test_ensure_single_setup_does_not_retry_after_failure():
    call_count = 0

    @ensure_single_setup
    def setup_func(app: FastAPI) -> None:
        nonlocal call_count
        call_count += 1
        msg = "boom"
        raise ValueError(msg)

    app = FastAPI()

    with pytest.raises(ValueError, match="boom"):
        setup_func(app)
    assert call_count == 1

    # subsequent calls do not retry: they raise immediately without
    # re-executing setup_func
    with pytest.raises(SetupAlreadyFailedError) as exc_info:
        setup_func(app)
    assert call_count == 1
    assert isinstance(exc_info.value.__cause__, ValueError)


def test_ensure_single_setup_success_after_other_app_failed():
    @ensure_single_setup
    def setup_func(app: FastAPI, *, should_fail: bool) -> None:
        if should_fail:
            msg = "boom"
            raise ValueError(msg)

    failing_app = FastAPI()
    with pytest.raises(ValueError, match="boom"):
        setup_func(failing_app, should_fail=True)

    # a different app instance is unaffected by another app's failure
    ok_app = FastAPI()
    setup_func(ok_app, should_fail=False)
    setup_func(ok_app, should_fail=False)  # idempotent no-op
