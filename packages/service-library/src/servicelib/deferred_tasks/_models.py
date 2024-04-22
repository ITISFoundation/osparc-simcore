from typing import Any, Literal, TypeAlias

from pydantic import BaseModel

TaskUID: TypeAlias = str  # Unique identifier provided by th MemoryManager
ClassUniqueReference: TypeAlias = str


class TaskResultSuccess(BaseModel):
    discriminator: Literal["success"] = "success"
    value: Any


class TaskResultError(BaseModel):
    discriminator: Literal["error"] = "error"
    # serializes an error form the worker: PC we need to talk on how to do this a bit better
    error: str
    str_traceback: str

    def format_error(self) -> str:
        return f"Execution raised '{self.error}':\n{self.str_traceback}"


class TaskResultCancelledError(BaseModel):
    discriminator: Literal["cancelled"] = "cancelled"


TaskExecutionResult: TypeAlias = (
    TaskResultSuccess | TaskResultError | TaskResultCancelledError
)
