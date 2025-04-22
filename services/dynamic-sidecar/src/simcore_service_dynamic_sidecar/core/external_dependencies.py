from common_library.errors_classes import OsparcErrorMixin
from fastapi import FastAPI
from servicelib.db_async_engine import connect_to_db
from servicelib.utils import logged_gather
from settings_library.postgres import PostgresSettings

from ..modules.service_liveness import wait_for_service_liveness
from .rabbitmq import wait_for_rabbitmq_liveness
from .registry import wait_for_registries_liveness
from .settings import ApplicationSettings
from .storage import wait_for_storage_liveness


class CouldNotReachExternalDependenciesError(OsparcErrorMixin, Exception):
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
        app_settings = app.state.settings
        assert isinstance(app_settings, ApplicationSettings)  # nosec
        postgres_settings = app_settings.POSTGRES_SETTINGS
        assert isinstance(postgres_settings, PostgresSettings)  # nosec
        liveliness_results = await logged_gather(
            *[
                wait_for_service_liveness(
                    connect_to_db,
                    app,
                    postgres_settings,
                    service_name="Postgres",
                    endpoint=postgres_settings.dsn,
                ),
                wait_for_rabbitmq_liveness(app),
                wait_for_registries_liveness(app),
                wait_for_storage_liveness(app),
            ],
            reraise=False,
        )
        failed = [f"{x}" for x in liveliness_results if isinstance(x, Exception)]
        if failed:
            raise CouldNotReachExternalDependenciesError(failed=failed)

    app.add_event_handler("startup", on_startup)
