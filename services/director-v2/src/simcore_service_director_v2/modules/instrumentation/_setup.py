from typing import cast

from fastapi import FastAPI
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)

from ...core.errors import ConfigurationError
from ._models import DirectorV2Instrumentation


def setup(app: FastAPI) -> None:
    registry = setup_prometheus_instrumentation(app)

    async def on_startup() -> None:
        app.state.instrumentation = DirectorV2Instrumentation(registry=registry)

    app.add_event_handler("startup", on_startup)


def get_instrumentation(app: FastAPI) -> DirectorV2Instrumentation:
    if not app.state.instrumentation:
        raise ConfigurationError(
            msg="Instrumentation not setup. Please check the configuration."
        )
    return cast(DirectorV2Instrumentation, app.state.instrumentation)
