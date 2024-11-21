import asyncio
import logging
from collections.abc import AsyncGenerator
from importlib.metadata import version
from typing import Any

import osparc_gateway_server
from aiodocker import Docker
from aiodocker.exceptions import DockerContainerError
from dask_gateway_server.backends.base import (  # type: ignore[import-untyped]
    PublicException,
)
from dask_gateway_server.backends.db_base import (  # type: ignore[import-untyped]
    Cluster,
    DBBackendBase,
    JobStatus,
    Worker,
    chain,
    islice,
    timestamp,
)

from ..remote_debug import setup_remote_debugging
from .errors import NoHostFoundError, NoServiceTasksError, TaskNotAssignedError
from .settings import AppSettings, BootModeEnum
from .utils import (
    OSPARC_SCHEDULER_API_PORT,
    DockerSecret,
    create_docker_secrets_from_tls_certs_for_cluster,
    delete_secrets,
    get_cluster_information,
    get_next_empty_node_hostname,
    get_osparc_scheduler_cmd_modifications,
    is_service_task_running,
    modify_cmd_argument,
    start_service,
    stop_service,
)

#
# https://patorjk.com/software/taag/#p=display&v=0&f=Avatar&t=osparc-gateway-server
#
WELCOME_MSG = rf"""
 ____  ____  ____  ____  ____  ____       ____  ____  ____  _  __      _____ ____  _____  _____ _      ____ ___  _      ____  _____ ____  _     _____ ____
/  _ \/ ___\/  __\/  _ \/  __\/   _\     /  _ \/  _ \/ ___\/ |/ /     /  __//  _ \/__ __\/  __// \  /|/  _ \\  \//     / ___\/  __//  __\/ \ |\/  __//  __\
| / \||    \|  \/|| / \||  \/||  / _____ | | \|| / \||    \|   /_____ | |  _| / \|  / \  |  \  | |  ||| / \| \  /_____ |    \|  \  |  \/|| | //|  \  |  \/|
| \_/|\___ ||  __/| |-|||    /|  \_\____\| |_/|| |-||\___ ||   \\____\| |_//| |-||  | |  |  /_ | |/\||| |-|| / / \____\\___ ||  /_ |    /| \// |  /_ |    /
\____/\____/\_/   \_/ \|\_/\_\\____/     \____/\_/ \|\____/\_|\_\     \____\\_/ \|  \_/  \____\\_/  \|\_/ \|/_/        \____/\____\\_/\_\\__/  \____\\_/\_\ {version(osparc_gateway_server.package_name)}


"""


class OsparcBackend(DBBackendBase):
    """A cluster backend that launches osparc workers.

    Scheduler are spawned as services in a docker swarm
    Workers are spawned as services in a docker swarm
    """

    settings: AppSettings
    docker_client: Docker
    cluster_secrets: list[DockerSecret] = []

    async def do_setup(self) -> None:
        self.settings = AppSettings()  # type: ignore[call-arg]
        assert isinstance(self.log, logging.Logger)  # nosec
        self.log.info(
            "osparc-gateway-server application settings:\n%s",
            self.settings.model_dump_json(indent=2),
        )

        if self.settings.SC_BOOT_MODE in [BootModeEnum.DEBUG]:
            setup_remote_debugging(logger=self.log)

        # pylint: disable=attribute-defined-outside-init
        self.cluster_start_timeout = self.settings.GATEWAY_CLUSTER_START_TIMEOUT
        self.worker_start_timeout = self.settings.GATEWAY_WORKER_START_TIMEOUT
        self.docker_client = Docker()

        print(WELCOME_MSG, flush=True)  # noqa: T201

    async def do_cleanup(self) -> None:
        assert isinstance(self.log, logging.Logger)  # nosec
        await self.docker_client.close()
        self.log.info("osparc-gateway-server closed.")

    async def do_start_cluster(
        self, cluster: Cluster
    ) -> AsyncGenerator[dict[str, Any], None]:
        assert isinstance(self.log, logging.Logger)  # nosec
        assert isinstance(self.api_url, str)  # nosec
        self.log.debug(f"starting {cluster=}")
        self.cluster_secrets.extend(
            await create_docker_secrets_from_tls_certs_for_cluster(
                self.docker_client, self, cluster
            )
        )
        self.log.debug("created '%s' for TLS certification", f"{self.cluster_secrets=}")

        # now we need a scheduler (get these auto-generated entries from dask-gateway base class)
        scheduler_env = self.get_scheduler_env(cluster)
        scheduler_cmd = self.get_scheduler_command(cluster)
        # we need a few modifications for running in docker swarm
        scheduler_service_name = f"cluster_{cluster.id}_scheduler"
        modifications = get_osparc_scheduler_cmd_modifications(scheduler_service_name)
        for key, value in modifications.items():
            scheduler_cmd = modify_cmd_argument(scheduler_cmd, key, value)
        # start the scheduler
        async for dask_scheduler_start_result in start_service(
            docker_client=self.docker_client,
            settings=self.settings,
            logger=self.log,
            service_name=scheduler_service_name,
            base_env=scheduler_env,
            cluster_secrets=[
                c for c in self.cluster_secrets if c.cluster.name == cluster.name
            ],
            cmd=scheduler_cmd,
            labels={"cluster_id": f"{cluster.id}", "type": "scheduler"},
            gateway_api_url=self.api_url,
            placement={"Constraints": ["node.role==manager"]},
        ):
            yield dask_scheduler_start_result

    async def do_stop_cluster(self, cluster: Cluster) -> None:
        assert isinstance(self.log, logging.Logger)  # nosec
        assert cluster.state  # nosec
        self.log.debug("--> stopping %s", f"{cluster=}")
        dask_scheduler_service_id = cluster.state.get("service_id")
        await stop_service(self.docker_client, dask_scheduler_service_id, self.log)
        await delete_secrets(self.docker_client, cluster)
        self.log.debug("<--%s stopped", f"{cluster=}")

    async def do_check_clusters(self, clusters: list[Cluster]) -> list[bool]:
        assert isinstance(self.log, logging.Logger)  # nosec
        self.log.debug("--> checking statuses of : %s", f"{clusters=}")
        oks: list[bool | BaseException] = await asyncio.gather(
            *[self._check_service_status(c) for c in clusters], return_exceptions=True
        )
        self.log.debug("<-- clusters status returned: %s", f"{oks=}")
        return [ok if isinstance(ok, bool) else False for ok in oks]

    async def do_start_worker(
        self, worker: Worker
    ) -> AsyncGenerator[dict[str, Any], None]:
        assert isinstance(self.log, logging.Logger)  # nosec
        assert isinstance(self.api_url, str)  # nosec
        assert worker.cluster  # nosec
        self.log.debug("--> starting %s", f"{worker=}")
        node_hostname = None
        try:
            node_hostname = await get_next_empty_node_hostname(
                self.docker_client, worker.cluster
            )
        except (NoServiceTasksError, TaskNotAssignedError) as exc:
            # this is a real error
            raise PublicException(f"{exc}") from exc
        except NoHostFoundError as exc:
            # this should not happen since calling do_start_worker is done
            # from the on_cluster_heartbeat that checks if we already reached max worker
            # What may happen is that a docker node was removed in between and that is an error we can report.
            msg = "Unexpected error while creating a new worker, there is no available host! Was a docker node removed?"
            raise PublicException(msg) from exc
        assert node_hostname is not None  # nosec
        worker_env = self.get_worker_env(worker.cluster)
        dask_scheduler_url = f"tls://cluster_{worker.cluster.id}_scheduler:{OSPARC_SCHEDULER_API_PORT}"  #  worker.cluster.scheduler_address
        # NOTE: the name must be set so that the scheduler knows which worker to wait for
        worker_env.update(
            {
                "DASK_SCHEDULER_URL": dask_scheduler_url,
                "DASK_WORKER_NAME": worker.name,
            }
        )

        async for dask_sidecar_start_result in start_service(
            docker_client=self.docker_client,
            settings=self.settings,
            logger=self.log,
            service_name=f"cluster_{worker.cluster.id}_sidecar_{worker.id}",
            base_env=worker_env,
            cluster_secrets=[
                c for c in self.cluster_secrets if c.cluster.name == worker.cluster.name
            ],
            cmd=None,
            labels={
                "cluster_id": f"{worker.cluster.id}",
                "worker_id": f"{worker.id}",
                "type": "worker",
            },
            gateway_api_url=self.api_url,
            placement={"Constraints": [f"node.hostname=={node_hostname}"]},
        ):
            yield dask_sidecar_start_result

    async def do_stop_worker(self, worker: Worker) -> None:
        assert isinstance(self.log, logging.Logger)  # nosec
        self.log.debug("--> Stopping %s", f"{worker=}")
        assert worker.state  # nosec
        if service_id := worker.state.get("service_id"):
            await stop_service(self.docker_client, service_id, self.log)
            self.log.debug("<-- %s stopped", f"{worker=}")
        else:
            self.log.error(
                "Worker %s does not have a service id! That is not expected!",
                f"{worker=}",
            )

    async def _check_service_status(self, cluster_service: Worker | Cluster) -> bool:
        assert isinstance(self.log, logging.Logger)  # nosec
        self.log.debug("--> checking status: %s", f"{cluster_service=}")
        assert cluster_service.state  # nosec
        if service_id := cluster_service.state.get("service_id"):
            self.log.debug("--> checking service '%s' status", f"{service_id}")
            try:
                service = await self.docker_client.services.inspect(service_id)
                if service:
                    service_name = service["Spec"]["Name"]
                    return await is_service_task_running(
                        self.docker_client, service_name, self.log
                    )

            except DockerContainerError:
                self.log.exception("Error while checking %s", f"{service_id=}")
        self.log.warning(
            "%s does not have a service id! That is not expected!",
            f"{cluster_service=}",
        )
        return False

    async def do_check_workers(self, workers: list[Worker]) -> list[bool]:
        assert isinstance(self.log, logging.Logger)  # nosec
        self.log.debug("--> checking statuses: %s", f"{workers=}")
        ok = await asyncio.gather(
            *[self._check_service_status(w) for w in workers], return_exceptions=True
        )
        self.log.debug("<-- worker status returned: %s", f"{ok=}")
        return [False if isinstance(_, BaseException) else _ for _ in ok]

    async def on_cluster_heartbeat(self, cluster_name, msg) -> None:
        # pylint: disable=no-else-continue, unused-variable, too-many-branches
        # pylint: disable=too-many-statements
        assert isinstance(self.log, logging.Logger)  # nosec

        # HACK: we override the base class heartbeat in order to
        # dynamically allow for more or less workers depending on the
        # available docker nodes!!!
        cluster = self.db.get_cluster(cluster_name)
        if cluster is None or cluster.target > JobStatus.RUNNING:
            return

        cluster.last_heartbeat = timestamp()

        if cluster.status == JobStatus.RUNNING:
            cluster_update = {}
        else:
            cluster_update = {
                "api_address": msg["api_address"],
                "scheduler_address": msg["scheduler_address"],
                "dashboard_address": msg["dashboard_address"],
            }

        count = msg["count"]
        active_workers = set(msg["active_workers"])
        closing_workers = set(msg["closing_workers"])
        closed_workers = set(msg["closed_workers"])

        self.log.info(
            "Cluster %s heartbeat [count: %d, n_active: %d, n_closing: %d, n_closed: %d]",
            cluster_name,
            count,
            len(active_workers),
            len(closing_workers),
            len(closed_workers),
        )

        # THIS IS THE HACK!!!
        # original code in dask_gateway_server.backend.db_base
        max_workers = cluster.config.get("cluster_max_workers")
        if self.settings.GATEWAY_SERVER_ONE_WORKER_PER_NODE:
            # cluster_max_workers = len(await get_cluster_information(self.docker_client))
            # if max_workers != cluster_max_workers:
            #     unfrozen_cluster_config = {k: v for k, v in cluster.config.items()}
            #     unfrozen_cluster_config["cluster_max_workers"] = cluster_max_workers
            #     cluster_update["config"] = unfrozen_cluster_config
            max_workers = len(await get_cluster_information(self.docker_client))
        if max_workers is not None and count > max_workers:
            # This shouldn't happen under normal operation, but could if the
            # user does something malicious (or there's a bug).
            self.log.info(
                "Cluster %s heartbeat requested %d workers, exceeding limit of %s.",
                cluster_name,
                count,
                max_workers,
            )
            count = max_workers

        if count != cluster.count:
            cluster_update["count"] = count

        created_workers = []
        submitted_workers = []
        target_updates = []
        newly_running = []
        close_expected = []
        for worker in cluster.workers.values():
            if worker.status >= JobStatus.STOPPED:
                continue
            if worker.name in closing_workers:
                if worker.status < JobStatus.RUNNING:
                    newly_running.append(worker)
                close_expected.append(worker)
            elif worker.name in active_workers:
                if worker.status < JobStatus.RUNNING:
                    newly_running.append(worker)
            elif worker.name in closed_workers:
                target = (
                    JobStatus.STOPPED if worker.close_expected else JobStatus.FAILED
                )
                target_updates.append((worker, {"target": target}))
            elif worker.status == JobStatus.SUBMITTED:
                submitted_workers.append(worker)
            else:
                assert worker.status == JobStatus.CREATED
                created_workers.append(worker)

        n_pending = len(created_workers) + len(submitted_workers)
        n_to_stop = len(active_workers) + n_pending - count
        if n_to_stop > 0:
            for w in islice(chain(created_workers, submitted_workers), n_to_stop):
                target_updates.append((w, {"target": JobStatus.STOPPED}))

        if cluster_update:
            self.db.update_cluster(cluster, **cluster_update)
            self.queue.put(cluster)

        self.db.update_workers(target_updates)
        for w, _u in target_updates:
            self.queue.put(w)

        if newly_running:
            # At least one worker successfully started, reset failure count
            cluster.worker_start_failure_count = 0
            self.db.update_workers(
                [(w, {"status": JobStatus.RUNNING}) for w in newly_running]
            )
            for w in newly_running:
                self.log.info("Worker %s is running", w.name)

        self.db.update_workers([(w, {"close_expected": True}) for w in close_expected])
