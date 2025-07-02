from typing import Generic, TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class ApiServerEnvelope(BaseModel, Generic[DataT]):
    data: DataT
