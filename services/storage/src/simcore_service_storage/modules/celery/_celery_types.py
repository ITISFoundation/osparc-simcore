from functools import partial
from pathlib import Path
from typing import Any

from kombu.utils.json import register_type  # type: ignore[import-untyped]
from models_library.api_schemas_storage.storage_schemas import (
    FileUploadCompletionBody,
    FoldersBody,
)
from pydantic import BaseModel

from ...models import FileMetaData


def _path_encoder(obj):
    if isinstance(obj, Path):
        return {"__path__": True, "path": str(obj)}
    return obj


# Define how Path objects are deserialized
def _path_decoder(obj):
    if "__path__" in obj:
        return Path(obj["path"])
    return obj


def _class_full_name(clz: type) -> str:
    return ".".join([clz.__module__, clz.__qualname__])


def _encoder(obj: BaseModel, *args, **kwargs) -> dict[str, Any]:
    return obj.model_dump(*args, **kwargs, mode="json")


def _decoder(clz: type[BaseModel], data: dict[str, Any]) -> BaseModel:
    return clz(**data)


def _register_pydantic_types(*models: type[BaseModel]) -> None:
    for model in models:
        register_type(
            model,
            _class_full_name(model),
            encoder=_encoder,
            decoder=partial(_decoder, model),
        )


def register_celery_types() -> None:
    register_type(
        Path,
        _class_full_name(Path),
        _path_encoder,
        _path_decoder,
    )
    _register_pydantic_types(FileUploadCompletionBody)
    _register_pydantic_types(FileMetaData)
    _register_pydantic_types(FoldersBody)
    register_type(set, _class_full_name(set), encoder=list, decoder=set)
