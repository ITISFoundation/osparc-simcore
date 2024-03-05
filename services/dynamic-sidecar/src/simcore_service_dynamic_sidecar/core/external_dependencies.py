from fastapi import FastAPI
from pydantic.errors import PydanticErrorMixin
from servicelib.utils import logged_gather

from .postgres import wait_for_postgres_liveness
from .rabbitmq import wait_for_rabbitmq_liveness
from .registry import wait_for_registry_liveness
from .storage import wait_for_storage_liveness


class CouldNotReachExternalDependenciesError(PydanticErrorMixin, Exception):
    msg_template: str = (
        "Could not start because the following external dependencies failed: {failed}"
    )


def setup_check_dependencies(app: FastAPI) -> None:
    # NOTE: in most situations these checks would live
    # inside each individual module's setup function
    # The dynamic-sidecar is created and expected to
    # start rapidly, for this reason they are run in
    # parallel.
    async def on_startup() -> None:
        liveliness_results = await logged_gather(
            *[
                wait_for_postgres_liveness(app),
                wait_for_rabbitmq_liveness(app),
                wait_for_registry_liveness(app),
                wait_for_storage_liveness(app),
            ],
            reraise=False,
        )
        failed = [f"{x}" for x in liveliness_results if isinstance(x, Exception)]
        if failed:
            raise CouldNotReachExternalDependenciesError(failed=failed)

    app.add_event_handler("startup", on_startup)
