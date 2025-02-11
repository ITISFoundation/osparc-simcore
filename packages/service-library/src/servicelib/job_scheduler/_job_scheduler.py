from datetime import datetime, timezone
from typing import Any

from servicelib.redis._client import RedisClientSDK

from ._client import JobName
from ._models import Priority, ScheduleID, WorkerID
from ._redis_job_scheduler_repository import RedisJobSchedulerRepository


class JobScheduler:
    def __init__(self, redis_client_sdk: RedisClientSDK) -> None:
        self._repository = RedisJobSchedulerRepository(redis_client_sdk)

    async def schedule(
        self, job_name: JobName, job_params: dict[str, Any], priority: Priority
    ) -> ScheduleID:
        pass

    async def dequeue(self, worker_id: WorkerID) -> ScheduleID | None:
        """
        - ho un worker morto heartbeat > 10 x 5 sec
            - si:  cerco tutte le schedule che ha attivo questo worker  doev lui owner
              - asseggno il nuovo worker_id
              - restituisco il schedule_id per il worker
            - no: non faccio  piu nulla
        - leggo le priotity queus
        - sort dellle key prento la piu importante
        - vedo se ho elementi in quella coda
         - si restituisco primo elemnto
         - no passo alla prossima coda meno imoportante e ripeto

        - se non trovo nulla restuitsco None (nulla da fare)
        """

        pass

    async def is_worker_alive(self, worker_id: WorkerID, max_inactive_time=60):
        last_heartbeat = await self._repository.get_worker_heartbeat(worker_id)
        if last_heartbeat:
            time_difference = datetime.now(timezone.utc) - last_heartbeat
            if time_difference.total_seconds() > max_inactive_time:
                return False
            return True
        return False

    async def setup(self) -> None:
        pass

    async def shutdown(self) -> None:
        pass


class JobSchedulerWorker:
    def __init__(self, job_scheduler: JobScheduler, worker_id: WorkerID) -> None:
        self._job_scheduler = job_scheduler
        self._worker_id = worker_id

        # worker4 gira ogni 5 secondi

    async def _worker(self) -> None:
        """
        1. ho ancura uno slot dispobibile per avviare un job? ( aggiorna il heartbet in redis)
        2 no = non faccio nulla
        3. si prendo elemnto dalla coda
        4. se ho un elemento da avviare lo avvio e scrivo che lo gestisco io
        """

        # leggere se posso avviare ancora
        schedule_id = await self._job_scheduler.dequeue(self._worker_id)
        if schedule_id is None:
            return

        # avvio il task
