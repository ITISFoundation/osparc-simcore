import logging
from typing import List

from fastapi import FastAPI
from jaeger_client import Config as jaeger_config
from opentracing.scope_managers.contextvars import ContextVarsScopeManager
from opentracing_instrumentation.client_hooks import install_all_patches
from starlette_opentracing import StarletteTracingMiddleWare

from scheduler import config
from scheduler.utils import AsyncTaskWrapper

logger = logging.getLogger(__name__)

app = FastAPI()

# imports all submodules to ensure service discovery
from scheduler import api as _  # pylint: disable=unused-import
from scheduler.core.enricher import wrapped_enricher_worker
from scheduler.dbs.mongo_models import initialize_mongo_driver


def configure_tracing():
    opentracing_config = jaeger_config(
        config={
            "sampler": {"type": "const", "param": 1},
            "logging": config.open_tracing_logging,
            "local_agent": {"reporting_host": config.jaeger_host},
        },
        scope_manager=ContextVarsScopeManager(),
        service_name="scheduler",
    )

    jaeger_tracer = opentracing_config.initialize_tracer()
    install_all_patches()
    app.add_middleware(StarletteTracingMiddleWare, tracer=jaeger_tracer)


wrapped_tasks: List[AsyncTaskWrapper] = []


@app.on_event("startup")
async def startup_event():
    configure_tracing()
    await initialize_mongo_driver()
    wrapped_tasks.append(wrapped_enricher_worker.start())

    logger.info("startup completed...")


@app.on_event("shutdown")
async def shutdown_event():
    for task in wrapped_tasks:
        await task.force_cleanup()
    logger.info("...shutdown finished")
