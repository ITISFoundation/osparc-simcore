import datetime
from enum import Enum, auto
from typing import Any, TypeAlias

from pydantic import BaseModel, NonNegativeInt

ScheduleID: TypeAlias = str
JobName: TypeAlias = str
Priority: TypeAlias = NonNegativeInt
WorkerID: TypeAlias = str


class JobStatus(Enum):
    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()


class JobResult:
    pass


class JobSchedule(BaseModel):
    schedule_id: ScheduleID | None = None

    priority: Priority = 0

    job_name: JobName | None = None
    job_params: dict[str, Any]
    job_status: JobStatus | None = None

    worker_id: WorkerID | None = None


class WorkersHeartbeat(BaseModel):
    worker_id: WorkerID
    last_beat: datetime.datetime  # in utc
