from pathlib import Path

from kombu.utils.json import register_type  # type: ignore[import-untyped]


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


def register_celery_types() -> None:
    register_type(
        Path,
        _class_full_name(Path),
        _path_encoder,
        _path_decoder,
    )
    register_type(set, _class_full_name(set), encoder=list, decoder=set)
