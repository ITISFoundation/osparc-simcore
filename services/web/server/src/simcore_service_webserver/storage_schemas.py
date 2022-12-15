from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, conint


class FileLocation(BaseModel):
    name: Optional[str] = None
    id: Optional[float] = None


class FileLocationArray(BaseModel):
    __root__: list[FileLocation]


class TableSynchronisation(BaseModel):
    dry_run: Optional[bool] = None
    fire_and_forget: Optional[bool] = None
    removed: list[str]


class Links(BaseModel):
    abort_upload: str
    complete_upload: str


class FileUploadSchema(BaseModel):
    chunk_size: conint(ge=0)
    urls: list[str]
    links: Links


class Links1(BaseModel):
    state: str


class FileUploadComplete(BaseModel):
    links: Links1


class State(Enum, str):
    ok = "ok"
    nok = "nok"


class FileUploadCompleteFuture(BaseModel):
    state: State
    e_tag: Optional[str] = None


class DatasetMetaData(BaseModel):
    dataset_id: Optional[str] = None
    display_name: Optional[str] = None


class DatasetMetaDataArray(BaseModel):
    __root__: list[DatasetMetaData]


class FileLocationEnveloped(BaseModel):
    data: FileLocation
    error: Optional[Any] = None


class TableSynchronisationEnveloped(BaseModel):
    data: TableSynchronisation
    error: Any


class FileUploadEnveloped(BaseModel):
    data: FileUploadSchema
    error: Any


class FileUploadCompleteEnveloped(BaseModel):
    data: FileUploadComplete
    error: Any


class FileUploadCompleteFutureEnveloped(BaseModel):
    data: FileUploadCompleteFuture
    error: Any


class DatasetMetaEnvelope(BaseModel):
    data: DatasetMetaData
    error: Optional[Any] = None
