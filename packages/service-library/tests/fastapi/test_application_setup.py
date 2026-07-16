from fastapi import FastAPI
from servicelib.fastapi.application_setup import ensure_single_setup


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
