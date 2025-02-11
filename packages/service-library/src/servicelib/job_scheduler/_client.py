from typing import Any

from ._models import JobName, JobStatus, ScheduleID, ScheduleResult


class ClientInterface:
    async def schedule(self, job_name: JobName, **kwargs: Any) -> ScheduleID:
        pass

    async def cancel(self, schedule_id: ScheduleID) -> None:
        pass

    async def status(self, schedule_id: ScheduleID) -> JobStatus:
        pass

    async def result(self, schedule_id: ScheduleID) -> ScheduleResult:
        pass
