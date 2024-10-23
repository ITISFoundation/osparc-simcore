from asyncio import Task

from pydantic import BaseModel, ConfigDict


class ResourceTrackingState(BaseModel):
    heart_beat_task: Task | None = None
    model_config = ConfigDict(arbitrary_types_allowed=True)
