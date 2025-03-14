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


def _class_full_name(clz: type[BaseModel]) -> str:
    return ".".join([clz.__module__, clz.__qualname__])


def _encoder(obj: BaseModel, *args, **kwargs) -> dict[str, Any]:
    return obj.model_dump(*args, **kwargs)


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
        ".".join([Path.__module__, Path.__qualname__]),
        _path_encoder,
        _path_decoder,
    )
