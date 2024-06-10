from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID


@dataclass(frozen=True)
class EfsManager:
    app: FastAPI

    _efs_mounted_path: Path
    _project_specific_data_base_directory: str

    @classmethod
    async def create(
        cls,
        app: FastAPI,
        efs_mounted_path: Path,
        project_specific_data_base_directory: str,
    ):
        return cls(app, efs_mounted_path, project_specific_data_base_directory)

    async def initialize_directories(self):
        _dir_path = self._efs_mounted_path / self._project_specific_data_base_directory
        Path.mkdir(_dir_path, parents=True, exist_ok=True)

    async def create_project_specific_data_dir(
        self, project_id: ProjectID, node_id: NodeID, storage_directory_name: str
    ) -> Path:
        _dir_path = (
            self._efs_mounted_path
            / self._project_specific_data_base_directory
            / f"{project_id}"
            / f"{node_id}"
            / f"{storage_directory_name}"
        )
        Path.mkdir(_dir_path, parents=True, exist_ok=True)
        return _dir_path
