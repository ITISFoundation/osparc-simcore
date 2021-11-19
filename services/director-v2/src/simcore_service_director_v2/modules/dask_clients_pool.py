import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterator, Dict

from fastapi import FastAPI
from models_library.clusters import Cluster, NoAuthentication
from servicelib.json_serialization import json_dumps
from simcore_postgres_database.models.clusters import ClusterType

from ..core.errors import ConfigurationError, DaskClientAcquisisitonError
from ..core.settings import DaskSchedulerSettings
from ..models.schemas.constants import ClusterID
from .dask_client import DaskClient

logger = logging.getLogger(__name__)


@dataclass
class DaskClientsPool:
    app: FastAPI
    settings: DaskSchedulerSettings
    _cluster_to_client_map: Dict[ClusterID, DaskClient] = field(default_factory=dict)

    @classmethod
    async def create(
        cls, app: FastAPI, settings: DaskSchedulerSettings
    ) -> "DaskClientsPool":
        new_instance = cls(app=app, settings=settings)
        # create default dask client
        default_cluster = Cluster(
            id=0,
            name="Internal Cluster",
            type=ClusterType.ON_PREMISE,
            endpoint=f"tcp://{settings.DASK_SCHEDULER_HOST}:{settings.DASK_SCHEDULER_PORT}",
            authentication=NoAuthentication(),
            owner=1,
        )
        async with new_instance.acquire(default_cluster):
            ...
        return new_instance

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
        try:
            # we create a new client if that cluster was never used before
            dask_client = self._cluster_to_client_map.setdefault(
                cluster.id,
                await DaskClient.create(
                    app=self.app,
                    settings=self.settings,
                    endpoint=cluster.endpoint,
                    authentication=cluster.authentication,
                ),
            )
            assert dask_client  # nosec
            yield dask_client
        except asyncio.CancelledError:
            logger.info("cancelled connection to dask computational cluster")
            raise
        except Exception as exc:
            logger.error(
                "could not create/access dask computational cluster %s",
                json_dumps(cluster),
            )
            raise DaskClientAcquisisitonError() from exc


def setup(app: FastAPI, settings: DaskSchedulerSettings) -> None:
    async def on_startup() -> None:
        app.state.dask_clients_pool = DaskClientsPool(app=app, settings=settings)

    async def on_shutdown() -> None:
        if app.state.dask_clients_pool:
            await app.state.dask_clients_pool.delete()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
