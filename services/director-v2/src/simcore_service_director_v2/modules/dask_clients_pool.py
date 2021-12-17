import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict, Optional

from fastapi import FastAPI
from models_library.clusters import Cluster, NoAuthentication
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.models.clusters import ClusterType

from ..core.errors import (
    ComputationalBackendNotConnectedError,
    ConfigurationError,
    DaskClientAcquisisitonError,
    InsuficientComputationalResourcesError,
    MissingComputationalResourcesError,
)
from ..core.settings import DaskSchedulerSettings
from ..models.schemas.constants import ClusterID
from .dask_client import DaskClient, TaskHandlers

logger = logging.getLogger(__name__)


@dataclass
class DaskClientsPool:
    app: FastAPI
    settings: DaskSchedulerSettings
    _client_acquisition_lock: asyncio.Lock = field(init=False)
    _cluster_to_client_map: Dict[ClusterID, DaskClient] = field(default_factory=dict)
    _task_handlers: Optional[TaskHandlers] = None

    def __post_init__(self):
        # NOTE: to ensure the correct loop is used
        self._client_acquisition_lock = asyncio.Lock()

    @staticmethod
    def default_cluster(settings: DaskSchedulerSettings):
        return Cluster(
            id=settings.DASK_DEFAULT_CLUSTER_ID,
            name="Default internal cluster",
            type=ClusterType.ON_PREMISE,
            endpoint=f"tcp://{settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
            authentication=NoAuthentication(),
            owner=1,  # FIXME: that is usually the everyone's group... but we do not know nor care about it in director-v2...
        )

    def register_handlers(self, task_handlers: TaskHandlers) -> None:
        self._task_handlers = task_handlers

    @classmethod
    async def create(
        cls, app: FastAPI, settings: DaskSchedulerSettings
    ) -> "DaskClientsPool":
        return cls(app=app, settings=settings)

    @staticmethod
    def instance(app: FastAPI) -> "DaskClientsPool":
        if not hasattr(app.state, "dask_clients_pool"):
            raise ConfigurationError(
                "Dask clients pool is " "not available. Please check the configuration."
            )
        return app.state.dask_clients_pool

    async def delete(self) -> None:
        await asyncio.gather(
            *[client.delete() for client in self._cluster_to_client_map.values()],
            return_exceptions=True,
        )

    @asynccontextmanager
    async def acquire(self, cluster: Cluster) -> AsyncIterator[DaskClient]:
        async def _concurently_safe_acquire_client() -> DaskClient:
            async with self._client_acquisition_lock:
                dask_client = self._cluster_to_client_map.get(cluster.id)

                # we create a new client if that cluster was never used before
                logger.debug(
                    "acquiring connection to cluster %s:%s", cluster.id, cluster.name
                )
                if not dask_client:
                    self._cluster_to_client_map[
                        cluster.id
                    ] = dask_client = await DaskClient.create(
                        app=self.app,
                        settings=self.settings,
                        endpoint=cluster.endpoint,
                        authentication=cluster.authentication,
                    )
                    if self._task_handlers:
                        dask_client.register_handlers(self._task_handlers)

                    logger.debug("created new client to cluster %s", f"{cluster=}")
                    logger.debug(
                        "list of clients: %s", f"{self._cluster_to_client_map=}"
                    )

                assert dask_client  # nosec
                return dask_client

        try:
            dask_client = await _concurently_safe_acquire_client()
            yield dask_client
        except (
            MissingComputationalResourcesError,
            InsuficientComputationalResourcesError,
        ):
            raise
        except (asyncio.CancelledError, ComputationalBackendNotConnectedError):
            # cleanup and re-raise
            if dask_client := self._cluster_to_client_map.pop(cluster.id, None):
                await dask_client.delete()
            raise
        except Exception as exc:
            # cleanup and re-raise
            if dask_client := self._cluster_to_client_map.pop(cluster.id, None):
                await dask_client.delete()
            logger.error(
                "could not create/access dask computational cluster %s",
                json_dumps(cluster),
            )
            raise DaskClientAcquisisitonError(cluster=cluster, error=exc) from exc


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    async def on_startup() -> None:
        app.state.dask_clients_pool = await DaskClientsPool.create(
            app=app, settings=settings
        )

    async def on_shutdown() -> None:
        if app.state.dask_clients_pool:
            await app.state.dask_clients_pool.delete()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
