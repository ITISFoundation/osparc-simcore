import tempfile
import threading
from pathlib import Path
from typing import Any, Union

from models_library.api_schemas_storage import FileID
from models_library.projects_nodes_io import LocationID

from . import config


def is_value_link(item_value: Union[int, float, bool, str, dict]) -> bool:
    # a link is composed of {nodeUuid:uuid, output:port_key}
    return isinstance(item_value, dict) and all(
        k in item_value for k in ("nodeUuid", "output")
    )


def is_value_on_store(item_value: Union[int, float, bool, str, dict]) -> bool:
    return isinstance(item_value, dict) and all(
        k in item_value for k in ("store", "path")
    )


def is_value_a_download_link(item_value: Union[int, float, bool, str, dict]) -> bool:
    return isinstance(item_value, dict) and all(
        k in item_value for k in ("downloadLink", "label")
    )


def is_file_type(item_type: str) -> bool:
    return f"{item_type}".startswith(config.FILE_TYPE_PREFIX)


def decode_link(value: dict) -> tuple[str, str]:
    return value["nodeUuid"], value["output"]


def decode_store(value: dict) -> tuple[LocationID, str]:
    return value["store"], value["path"]


def encode_store(store: LocationID, s3_object: FileID) -> dict[str, Any]:
    return {"store": store, "path": s3_object}


def encode_file_id(file_path: Path, project_id: str, node_id: str) -> FileID:
    return FileID(f"{project_id}/{node_id}/{file_path.name}")


_INTERNAL_DIR = Path(tempfile.gettempdir(), "simcorefiles")


def create_folder_path(key: str) -> Path:
    return Path(_INTERNAL_DIR, f"{threading.get_ident()}", key)


def create_file_path(key: str, name: str) -> Path:
    return Path(_INTERNAL_DIR, f"{threading.get_ident()}", key, name)
