import tempfile
from pathlib import Path
from typing import Final
from uuid import uuid4

from models_library.projects_nodes_io import SimcoreS3FileID

_TMP_SIMCOREFILES: Final[Path] = Path(tempfile.gettempdir()) / "simcorefiles"


def create_simcore_file_id(
    file_path: Path,
    project_id: str,
    node_id: str,
    *,
    file_base_path: Path | None = None,
) -> SimcoreS3FileID:
    s3_file_name = file_path.name
    if file_base_path:
        s3_file_name = f"{file_base_path / file_path.name}"
    clean_path = Path(f"{project_id}/{node_id}/{s3_file_name}")
    return SimcoreS3FileID(f"{clean_path}")


def get_folder_path(key: str) -> Path:
    return _TMP_SIMCOREFILES / f"{uuid4()}" / key


def get_file_path(key: str, name: str) -> Path:
    return _TMP_SIMCOREFILES / f"{uuid4()}" / key / name
