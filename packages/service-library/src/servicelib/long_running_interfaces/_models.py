import hashlib
import json
from enum import auto
from functools import cached_property
from typing import Any, Self, TypeAlias

from models_library.utils.enums import StrAutoEnum
from pydantic import BaseModel, field_validator, model_validator

LongRunningNamespace: TypeAlias = str

RemoteHandlerName: TypeAlias = str
CorrelationID: TypeAlias = str
JobUniqueId: TypeAlias = str

StartParams: TypeAlias = dict[str, Any]


def _sort_dict(data: dict) -> dict:
    return dict(sorted(data.items()))


class UniqueIdModel(BaseModel):
    name: RemoteHandlerName
    correlation_id: CorrelationID
    params: dict[str, Any]

    @field_validator("params", mode="before")
    @classmethod
    def sort_params(cls, value: dict[str, Any]) -> dict[str, Any]:
        return _sort_dict(value)

    @cached_property
    def unique_id(self) -> JobUniqueId:
        data = self.model_dump(mode="json")
        serialized = json.dumps(_sort_dict(data), sort_keys=True, separators=(",", ":"))
        return hashlib.sha512(serialized.encode()).hexdigest()


class ErrorModel(BaseModel):
    error_message: str
    traceback: str


class ResultModel(BaseModel):
    data: Any | None = None
    error: ErrorModel | None = None

    @model_validator(mode="after")
    def ensure_consistency(self: Self) -> Self:
        if self.error is not None and self.data is not None:
            msg = f"when {self.error=} is not None, {self.data=} can't be set"
            raise ValueError(msg)
        return self


class JobStatus(StrAutoEnum):
    NOT_FOUND = auto()
    RUNNING = auto()
    FINISHED = auto()


class ScheduleModel(BaseModel):
    name: RemoteHandlerName
    correlation_id: CorrelationID
    params: dict[str, Any]

    remaining_attempts: int
