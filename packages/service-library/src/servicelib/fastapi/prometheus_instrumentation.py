# pylint: disable=protected-access


from fastapi import FastAPI
from prometheus_client import CollectorRegistry
from prometheus_fastapi_instrumentator import Instrumentator


def setup_prometheus_instrumentation(app: FastAPI) -> Instrumentator:
    # NOTE: use that registry to prevent having a global one
    app.state.prometheus_registry = registry = CollectorRegistry(auto_describe=True)
    instrumentator = Instrumentator(
        should_instrument_requests_inprogress=False,  # bug in https://github.com/trallnag/prometheus-fastapi-instrumentator/issues/317
        inprogress_labels=False,
        registry=registry,
    ).instrument(app)

    async def _on_startup() -> None:
        instrumentator.expose(app, include_in_schema=False)

    def _unregister() -> None:
        # NOTE: avoid registering collectors multiple times when running unittests consecutively (https://stackoverflow.com/a/62489287)
        for collector in list(registry._collector_to_names.keys()):  # noqa: SLF001
            registry.unregister(collector)

    app.add_event_handler("startup", _on_startup)
    app.add_event_handler("shutdown", _unregister)
    return instrumentator
