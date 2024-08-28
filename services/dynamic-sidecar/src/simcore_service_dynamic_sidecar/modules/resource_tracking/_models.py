from asyncio import Task

from pydantic.v1 import BaseModel


class ResourceTrackingState(BaseModel):
    heart_beat_task: Task | None = None

    class Config:
        arbitrary_types_allowed = True
