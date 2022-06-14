import tempfile
import threading
from pathlib import Path

from models_library.projects_nodes_io import SimcoreS3FileID


def create_simcore_file_id(
    file_path: Path, project_id: str, node_id: str
) -> SimcoreS3FileID:
    return SimcoreS3FileID(f"{project_id}/{node_id}/{file_path.name}")


_INTERNAL_DIR = Path(tempfile.gettempdir(), "simcorefiles")


def create_folder_path(key: str) -> Path:
    return Path(_INTERNAL_DIR, f"{threading.get_ident()}", key)


def create_file_path(key: str, name: str) -> Path:
    return Path(_INTERNAL_DIR, f"{threading.get_ident()}", key, name)
