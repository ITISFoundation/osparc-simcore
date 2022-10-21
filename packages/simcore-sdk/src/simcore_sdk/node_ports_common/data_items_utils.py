import contextlib
import tempfile
import threading
from pathlib import Path
from typing import Optional

from models_library.projects_nodes_io import SimcoreS3FileID


def create_simcore_file_id(
    file_path: Path,
    project_id: str,
    node_id: str,
    *,
    file_base_path: Optional[Path] = None,
) -> SimcoreS3FileID:
    s3_file_name = file_path.name
    if file_base_path:
        with contextlib.suppress(ValueError):
            s3_file_name = file_path.relative_to(file_base_path)

    return SimcoreS3FileID(f"{project_id}/{node_id}/{s3_file_name}")


_INTERNAL_DIR = Path(tempfile.gettempdir(), "simcorefiles")


def create_folder_path(key: str) -> Path:
    return Path(_INTERNAL_DIR, f"{threading.get_ident()}", key)


def create_file_path(key: str, name: str) -> Path:
    return Path(_INTERNAL_DIR, f"{threading.get_ident()}", key, name)
