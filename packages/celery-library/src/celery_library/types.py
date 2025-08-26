from functools import partial
from pathlib import Path
from typing import Any

from kombu.utils.json import register_type  # type: ignore[import-untyped]
from pydantic import BaseModel


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


def _pydantic_model_encoder(obj: BaseModel, *args, **kwargs) -> dict[str, Any]:
    return obj.model_dump(*args, **kwargs, mode="json")


def _pydantic_model_decoder(clz: type[BaseModel], data: dict[str, Any]) -> BaseModel:
    return clz(**data)


def register_celery_types() -> None:
    register_type(
        Path,
        _class_full_name(Path),
        _path_encoder,
        _path_decoder,
    )
    register_type(set, _class_full_name(set), encoder=list, decoder=set)


def register_pydantic_types(*models: type[BaseModel]) -> None:
    for model in models:
        register_type(
            model,
            _class_full_name(model),
            encoder=_pydantic_model_encoder,
            decoder=partial(_pydantic_model_decoder, model),
        )
