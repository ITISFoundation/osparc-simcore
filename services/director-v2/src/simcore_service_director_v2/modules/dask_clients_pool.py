import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Optional

from fastapi import FastAPI
from models_library.clusters import Cluster, ClusterID

from ..core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalSchedulerChangedError,
    ConfigurationError,
    DaskClientAcquisisitonError,
)
from ..core.settings import ComputationalBackendSettings
from .dask_client import DaskClient, TaskHandlers

logger = logging.getLogger(__name__)


@dataclass
class DaskClientsPool:
    app: FastAPI
    settings: ComputationalBackendSettings
    _client_acquisition_lock: asyncio.Lock = field(init=False)
    _cluster_to_client_map: dict[ClusterID, DaskClient] = field(default_factory=dict)
    _task_handlers: Optional[TaskHandlers] = None

    def __post_init__(self):
        # NOTE: to ensure the correct loop is used
        self._client_acquisition_lock = asyncio.Lock()

    def register_handlers(self, task_handlers: TaskHandlers) -> None:
        self._task_handlers = task_handlers

    @classmethod
    async def create(
        cls, app: FastAPI, settings: ComputationalBackendSettings
    ) -> "DaskClientsPool":
        return cls(app=app, settings=settings)

    @staticmethod
    def instance(app: FastAPI) -> "DaskClientsPool":
        if not hasattr(app.state, "dask_clients_pool"):
            raise ConfigurationError(
                "Dask clients pool is not available. Please check the configuration."
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
                assert isinstance(cluster.id, int)  # nosec
                dask_client = self._cluster_to_client_map.get(cluster.id)

                # we create a new client if that cluster was never used before
                logger.debug(
                    "acquiring connection to cluster %s:%s", cluster.id, cluster.name
                )
                if not dask_client:
                    tasks_file_link_type = (
                        self.settings.COMPUTATIONAL_BACKEND_DEFAULT_FILE_LINK_TYPE
                    )
                    if cluster == self.settings.default_cluster:
                        tasks_file_link_type = (
                            self.settings.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_FILE_LINK_TYPE
                        )
                    self._cluster_to_client_map[
                        cluster.id
                    ] = dask_client = await DaskClient.create(
                        app=self.app,
                        settings=self.settings,
                        endpoint=cluster.endpoint,
                        authentication=cluster.authentication,
                        tasks_file_link_type=tasks_file_link_type,
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
        except Exception as exc:
            raise DaskClientAcquisisitonError(cluster=cluster, error=exc) from exc

        try:
            yield dask_client
        except (
            asyncio.CancelledError,
            ComputationalBackendNotConnectedError,
            ComputationalSchedulerChangedError,
        ):
            # cleanup and re-raise
            if dask_client := self._cluster_to_client_map.pop(cluster.id, None):
                await dask_client.delete()
            raise


def setup(app: FastAPI, settings: ComputationalBackendSettings) -> None:
    async def on_startup() -> None:
        app.state.dask_clients_pool = await DaskClientsPool.create(
            app=app, settings=settings
        )

        logger.info(
            "Default cluster is set to %s",
            f"{settings.default_cluster!r}",
        )

    async def on_shutdown() -> None:
        if app.state.dask_clients_pool:
            await app.state.dask_clients_pool.delete()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
