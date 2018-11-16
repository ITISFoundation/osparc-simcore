import tempfile
from pathlib import Path
from typing import Dict, Tuple

from . import config


def is_value_link(item_value: str) -> bool:
    # a link is composed of {nodeUuid:uuid, output:port_key}
    return isinstance(item_value, dict) and all(k in item_value for k in ("nodeUuid", "output"))

def is_value_on_store(item_value: str) -> bool:
    return isinstance(item_value, dict) and all(k in item_value for k in ("store", "path"))

def is_file_type(item_type: str) -> bool:
    return str(item_type).startswith(config.FILE_TYPE_PREFIX)

def decode_link(value: Dict) -> Tuple[str, str]:
    return value["nodeUuid"], value["output"]

def decode_store(value: Dict)->Tuple[str, str]:
    return value["store"], value["path"]

def encode_store(store:str, s3_object:str) -> Dict:
    return {"store":str(store), "path":s3_object}

def encode_file_id(file_path: Path, project_id: str, node_id: str) -> str:
    file_id = "{}/{}/{}".format(project_id, node_id, file_path.name)
    return file_id

_INTERNAL_DIR = Path(tempfile.gettempdir(), "simcorefiles")
def create_file_path(key:str, name:str) -> Path:
    return Path(_INTERNAL_DIR, key, name)
