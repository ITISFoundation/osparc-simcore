# pylint: disable=protected-access


from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi_lifespan_manager import State
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator


def initialize_prometheus_instrumentation(app: FastAPI) -> None:
    # NOTE: this cannot be ran once the application is started

    # NOTE: use that registry to prevent having a global one
    app.state.prometheus_registry = registry = CollectorRegistry(auto_describe=True)
    app.state.prometheus_instrumentator = Instrumentator(
        should_instrument_requests_inprogress=False,  # bug in https://github.com/trallnag/prometheus-fastapi-instrumentator/issues/317
        inprogress_labels=False,
        registry=registry,
    )
    app.state.prometheus_instrumentator.instrument(app)


def _startup(app: FastAPI) -> None:
    assert isinstance(app.state.prometheus_instrumentator, Instrumentator)  # nosec
    app.state.prometheus_instrumentator.expose(app, include_in_schema=False)


def _shutdown(app: FastAPI) -> None:
    assert isinstance(app.state.prometheus_registry, CollectorRegistry)  # nosec
    registry = app.state.prometheus_registry
    for collector in list(registry._collector_to_names.keys()):  # noqa: SLF001
        registry.unregister(collector)


def get_prometheus_instrumentator(app: FastAPI) -> Instrumentator:
    assert isinstance(app.state.prometheus_instrumentator, Instrumentator)  # nosec
    return app.state.prometheus_instrumentator


def setup_prometheus_instrumentation(app: FastAPI) -> Instrumentator:
    initialize_prometheus_instrumentation(app)

    async def _on_startup() -> None:
        _startup(app)

    def _on_shutdown() -> None:
        _shutdown(app)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _on_shutdown)

    return get_prometheus_instrumentator(app)


async def lifespan_prometheus_instrumentation(app: FastAPI) -> AsyncIterator[State]:
    # NOTE: requires ``initialize_prometheus_instrumentation`` to be called before the
    # lifespan of the applicaiton runs, usually rigth after the ``FastAPI`` instance is created
    _startup(app)
    yield {}
    _shutdown(app)
