import logging
from contextlib import contextmanager
from copy import deepcopy
from typing import Any, Final, Iterator

import docker
import simcore_postgres_database.cli
import sqlalchemy as sa
from docker.models.services import Service
from simcore_postgres_database.models.base import metadata
from tenacity import TryAgain, retry
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

log = logging.getLogger(__name__)


_MINUTE: Final[int] = 60
_LOG_HEAD_MIGRATION: Final[str] = "Migration service"


def _get_migration_service(docker_client: docker.DockerClient) -> Service | None:
    service: Service
    for service in docker_client.services.list(
        filters={"name": "pytest-simcore_migration"}
    ):
        return service

    return None


def _was_migration_service_started(docker_client: docker.DockerClient) -> bool:
    service: Service | None = _get_migration_service(docker_client)
    return service is not None


def _did_migration_service_finished_postgres_migration(
    docker_client: docker.DockerClient,
) -> bool:
    service: Service | None = _get_migration_service(docker_client)
    assert service is not None

    logs = [x.decode() for x in service.logs(stdout=True)]
    return "Migration Done. Wait forever ..." in "\n".join(logs)


@retry(
    wait=wait_fixed(0.5),
    stop=stop_after_delay(2 * _MINUTE),
    before_sleep=before_sleep_log(log, logging.WARNING),
    reraise=True,
)
def wait_for_migration_service(docker_client: docker.DockerClient) -> None:
    if not _did_migration_service_finished_postgres_migration(docker_client):
        raise TryAgain(f"{_LOG_HEAD_MIGRATION} did not finish Postgres migration")


@contextmanager
def migrated_pg_tables_context(
    docker_client: docker.DockerClient, postgres_config: dict[str, str]
) -> Iterator[dict[str, Any]]:
    """
    Within the context, tables are created and dropped
    using migration upgrade/downgrade routines
    """

    cfg = deepcopy(postgres_config)
    cfg.update(
        dsn="postgresql://{user}:{password}@{host}:{port}/{database}".format(
            **postgres_config
        )
    )

    # NOTE: if migration service was also started we should wait for the service
    # to finish migrating Postgres, before trying to run the migrations again
    if _was_migration_service_started(docker_client):
        log.info("%s is running, attending for it to be idle", _LOG_HEAD_MIGRATION)
        wait_for_migration_service(docker_client)
        log.info("%s is now idle!", _LOG_HEAD_MIGRATION)
    else:
        log.info("%s is not present", _LOG_HEAD_MIGRATION)

    simcore_postgres_database.cli.discover.callback(**postgres_config)
    simcore_postgres_database.cli.upgrade.callback("head")

    yield cfg

    # downgrades database to zero ---
    #
    # NOTE: This step CANNOT be avoided since it would leave the db in an invalid state
    # E.g. 'alembic_version' table is not deleted and keeps head version or routines
    # like 'notify_comp_tasks_changed' remain undeleted
    #
    simcore_postgres_database.cli.downgrade.callback("base")
    simcore_postgres_database.cli.clean.callback()  # just cleans discover cache

    # FIXME: migration downgrade fails to remove User types
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/1776
    # Added drop_all as tmp fix
    postgres_engine = sa.create_engine(cfg["dsn"])
    metadata.drop_all(bind=postgres_engine)


def is_postgres_responsive(url) -> bool:
    """Check if something responds to ``url``"""
    try:
        engine = sa.create_engine(url)
        conn = engine.connect()
        conn.close()
    except sa.exc.OperationalError:
        return False
    return True
