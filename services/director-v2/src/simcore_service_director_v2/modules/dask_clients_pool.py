import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import TypeAlias

from fastapi import FastAPI
from models_library.clusters import BaseCluster, ClusterTypeInModel
from pydantic import AnyUrl
from servicelib.logging_utils import log_context
from servicelib.redis._semaphore_decorator import with_limited_concurrency
from settings_library.redis import RedisDatabase
from simcore_service_director_v2.modules.comp_scheduler._utils import (
    get_redis_lock_key,
)
from simcore_service_director_v2.modules.redis import get_redis_client_manager

from ..core.errors import (
    ComputationalBackendNotConnectedError,
    ComputationalSchedulerChangedError,
    ConfigurationError,
    DaskClientAcquisisitonError,
)
from ..core.settings import ComputationalBackendSettings
from ..utils.dask_client_utils import TaskHandlers
from .dask_client import DaskClient

_logger = logging.getLogger(__name__)


_ClusterUrl: TypeAlias = AnyUrl
ClientRef: TypeAlias = str


@dataclass
class DaskClientsPool:
    app: FastAPI
    settings: ComputationalBackendSettings
    _client_acquisition_lock: asyncio.Lock = field(init=False)
    _cluster_to_client_map: dict[_ClusterUrl, DaskClient] = field(default_factory=dict)
    _task_handlers: TaskHandlers | None = None
    # Track references to each client by endpoint
    _client_to_refs: defaultdict[_ClusterUrl, set[ClientRef]] = field(
        default_factory=lambda: defaultdict(set)
    )
    _ref_to_clients: dict[ClientRef, _ClusterUrl] = field(default_factory=dict)

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
            msg = "Dask clients pool is not available. Please check the configuration."
            raise ConfigurationError(msg=msg)
        dask_clients_pool: DaskClientsPool = app.state.dask_clients_pool
        return dask_clients_pool

    async def delete(self) -> None:
        await asyncio.gather(
            *[client.delete() for client in self._cluster_to_client_map.values()],
            return_exceptions=True,
        )
        self._cluster_to_client_map.clear()
        self._client_to_refs.clear()
        self._ref_to_clients.clear()

    async def release_client_ref(self, ref: ClientRef) -> None:
        """Release a dask client reference by its ref.

        If all the references to the client are released,
        the client will be deleted from the pool.
        This method is thread-safe and can be called concurrently.
        """
        async with self._client_acquisition_lock:
            # Find which endpoint this ref belongs to
            if cluster_endpoint := self._ref_to_clients.pop(ref, None):
                # we have a client, remove our reference and check if there are any more references
                assert ref in self._client_to_refs[cluster_endpoint]  # nosec
                self._client_to_refs[cluster_endpoint].discard(ref)

                # If we found an endpoint with no more refs, clean it up
                if not self._client_to_refs[cluster_endpoint] and (
                    dask_client := self._cluster_to_client_map.pop(
                        cluster_endpoint, None
                    )
                ):
                    _logger.info(
                        "Last reference to client %s released, deleting client",
                        cluster_endpoint,
                    )
                    await dask_client.delete()
                    _logger.debug(
                        "Remaining clients: %s",
                        [f"{k}" for k in self._cluster_to_client_map],
                    )

    @asynccontextmanager
    async def acquire(
        self, cluster: BaseCluster, *, ref: ClientRef
    ) -> AsyncIterator[DaskClient]:
        """Returns a dask client for the given cluster.

        This method is thread-safe and can be called concurrently.
        If the cluster is not found in the pool, it will create a new dask client for it.

        The passed reference is used to track the client usage, user should call
        `release_client_ref` to release the client reference when done.
        """

        @with_limited_concurrency(
            get_redis_client_manager(self.app).client(RedisDatabase.LOCKS),
            key=get_redis_lock_key(
                "dask-clients-pool",
                unique_lock_key_builder=lambda: f"{cluster.name}-{cluster.endpoint}",
            ),
            capacity=20,
            blocking=True,
            blocking_timeout=None,
        )
        async def _concurently_safe_acquire_client() -> DaskClient:
            async with self._client_acquisition_lock:
                with log_context(
                    _logger,
                    logging.DEBUG,
                    f"acquire dask client for {cluster.name=}:{cluster.endpoint}",
                ):
                    dask_client = self._cluster_to_client_map.get(cluster.endpoint)
                    if not dask_client:
                        tasks_file_link_type = (
                            self.settings.COMPUTATIONAL_BACKEND_DEFAULT_FILE_LINK_TYPE
                        )
                        if cluster == self.settings.default_cluster:
                            tasks_file_link_type = (
                                self.settings.COMPUTATIONAL_BACKEND_DEFAULT_CLUSTER_FILE_LINK_TYPE
                            )
                        if cluster.type == ClusterTypeInModel.ON_DEMAND.value:
                            tasks_file_link_type = (
                                self.settings.COMPUTATIONAL_BACKEND_ON_DEMAND_CLUSTERS_FILE_LINK_TYPE
                            )
                        self._cluster_to_client_map[cluster.endpoint] = dask_client = (
                            await DaskClient.create(
                                app=self.app,
                                settings=self.settings,
                                endpoint=cluster.endpoint,
                                authentication=cluster.authentication,
                                tasks_file_link_type=tasks_file_link_type,
                                cluster_type=cluster.type,
                            )
                        )
                        if self._task_handlers:
                            dask_client.register_handlers(self._task_handlers)

                    # Track the reference
                    self._client_to_refs[cluster.endpoint].add(ref)
                    self._ref_to_clients[ref] = cluster.endpoint

                    _logger.debug(
                        "Client %s now has %d references",
                        cluster.endpoint,
                        len(self._client_to_refs[cluster.endpoint]),
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
            if dask_client := self._cluster_to_client_map.pop(cluster.endpoint, None):  # type: ignore[arg-type] # https://github.com/python/mypy/issues/10152
                await dask_client.delete()
            raise


def setup(app: FastAPI, settings: ComputationalBackendSettings) -> None:
    async def on_startup() -> None:
        app.state.dask_clients_pool = await DaskClientsPool.create(
            app=app, settings=settings
        )

        _logger.info(
            "Default cluster is set to %s",
            f"{settings.default_cluster!r}",
        )

    async def on_shutdown() -> None:
        if app.state.dask_clients_pool:
            await app.state.dask_clients_pool.delete()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)
