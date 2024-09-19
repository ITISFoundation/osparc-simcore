# pylint: disable=protected-access


from fastapi import FastAPI
from prometheus_fastapi_instrumentator import Instrumentator


def setup_prometheus_instrumentation(app: FastAPI) -> Instrumentator:

    instrumentator = Instrumentator(
        should_instrument_requests_inprogress=True, inprogress_labels=False
    ).instrument(app)

    async def on_startup(app: FastAPI) -> None:
        instrumentator.expose(app, include_in_schema=False)

    def _unregister() -> None:
        # NOTE: avoid registering collectors multiple times when running unittests consecutively (https://stackoverflow.com/a/62489287)
        for collector in list(
            instrumentator.registry._collector_to_names.keys()  # noqa: SLF001
        ):
            instrumentator.registry.unregister(collector)

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", _unregister)
    return instrumentator
