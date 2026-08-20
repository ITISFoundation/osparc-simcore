from collections.abc import AsyncIterator

from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from fastapi_lifespan_manager import LifespanManager
from servicelib.utils import logged_gather

from ..modules.database import wait_for_database_liveness
from .rabbitmq import wait_for_rabbitmq_liveness
from .registry import wait_for_registries_liveness
from .storage import wait_for_storage_liveness


class CouldNotReachExternalDependenciesError(OsparcErrorMixin, Exception):
    msg_template: str = "Could not start because the following external dependencies failed: {failed}"


async def _check_dependencies(app: FastAPI) -> None:
    liveliness_results = await logged_gather(
        *[
            wait_for_database_liveness(app),
            wait_for_rabbitmq_liveness(app),
            wait_for_registries_liveness(app),
            wait_for_storage_liveness(app),
        ],
        reraise=False,
    )
    failed = [f"{result}" for result in liveliness_results if isinstance(result, Exception)]
    if failed:
        raise CouldNotReachExternalDependenciesError(failed=failed)


async def _check_dependencies_lifespan(app: FastAPI) -> AsyncIterator[None]:
    await _check_dependencies(app)
    yield


def configure_check_dependencies(app_lifespan: LifespanManager[FastAPI]) -> None:
    app_lifespan.add(_check_dependencies_lifespan)
