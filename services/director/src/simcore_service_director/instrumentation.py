from fastapi import FastAPI
from servicelib.fastapi.prometheus_instrumentation import (
    setup_prometheus_instrumentation,
)

from .core.settings import get_application_settings


def setup(app: FastAPI) -> None:
    app_settings = get_application_settings(app)
    if not app_settings.DIRECTOR_MONITORING_ENABLED:
        return

    # NOTE: this must be setup before application startup
    instrumentator = setup_prometheus_instrumentation(app)

    async def on_startup() -> None:
        # metrics_subsystem = (
        #     "dynamic" if app_settings.AUTOSCALING_NODES_MONITORING else "computational"
        # )
        # app.state.instrumentation = (
        #     AutoscalingInstrumentation(  # pylint: disable=unexpected-keyword-arg
        #         registry=instrumentator.registry, subsystem=metrics_subsystem
        #     )
        # )
        ...

    async def on_shutdown() -> None:
        ...

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


# def get_instrumentation(app: FastAPI) -> AutoscalingInstrumentation:
#     if not app.state.instrumentation:
#         raise ConfigurationError(
#             msg="Instrumentation not setup. Please check the configuration."
#         )
#     return cast(AutoscalingInstrumentation, app.state.instrumentation)


def has_instrumentation(app: FastAPI) -> bool:
    return hasattr(app.state, "instrumentation")
