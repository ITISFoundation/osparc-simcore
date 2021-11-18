import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import AsyncIterable, AsyncIterator, Dict

from fastapi import FastAPI
from models_library.clusters import Cluster
from servicelib.json_serialization import json_dumps

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

    @staticmethod
    def instance(app: FastAPI) -> "DaskClientsPool":
        if not hasattr(app.state, "dask_clients_pool"):
            raise ConfigurationError(
                "Dask clients pool is " "not available. Please check the configuration."
            )
        return app.state.dask_clients_pool

    @asynccontextmanager
    async def acquire(self, cluster: Cluster) -> AsyncIterator[DaskClient]:
        try:
            dask_client = self._cluster_to_client_map.setdefault(
                cluster.id,
                await DaskClient.create(app=self.app, settings=self.settings),
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
        app.state.dask_clients_pool = DaskClientsPool(app, settings)

    async def on_shutdown() -> None:
        ...
        # nothing for now
        # if app.state.dask_clients_pool:
        #     del app.state.dask_clients_pool  # type: ignore

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
