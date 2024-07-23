from typing import Any, Literal, TypeAlias

from models_library.basic_types import IDStr
from pydantic import BaseModel

TaskUID: TypeAlias = IDStr  # Unique identifier provided by the TaskTracker
ClassUniqueReference: TypeAlias = str


class TaskResultSuccess(BaseModel):
    result_type: Literal["success"] = "success"
    value: Any


class TaskResultError(BaseModel):
    result_type: Literal["error"] = "error"
    # serialized error from the worker
    error: str
    str_traceback: str

    def format_error(self) -> str:
        return f"Execution raised '{self.error}':\n{self.str_traceback}"


class TaskResultCancelledError(BaseModel):
    result_type: Literal["cancelled"] = "cancelled"


TaskExecutionResult: TypeAlias = (
    TaskResultSuccess | TaskResultError | TaskResultCancelledError
)
