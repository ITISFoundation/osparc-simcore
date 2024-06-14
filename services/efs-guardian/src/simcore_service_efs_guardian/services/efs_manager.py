import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

_EFS_LINUX_USER = 8006
_EFS_GROUP_LINUX_GROUP = 8106


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

        # Temporary
        await self.create_project_specific_data_dir(
            project_id="24acabca-e57e-428b-aa69-7aaf33c5425f",
            node_id="24acabca-e57e-428b-aa69-7aaf33c5425f",
            storage_directory_name="matus",
        )

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
        # Ensure the directory exists with the right parents
        Path.mkdir(_dir_path, parents=True, exist_ok=True)
        # Change the owner to user id 8006(efs) and group id 8106(efs-group)
        os.chown(_dir_path, _EFS_LINUX_USER, _EFS_GROUP_LINUX_GROUP)
        # Set directory permissions to allow group write access
        os.chmod(
            _dir_path, 0o770
        )  # This gives rwx permissions to user and group, and nothing to others
        return _dir_path
