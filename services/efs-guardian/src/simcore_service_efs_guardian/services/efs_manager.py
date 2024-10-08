import os
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import ByteSize

from ..core.settings import ApplicationSettings, get_application_settings
from . import efs_manager_utils


@dataclass(frozen=True)
class EfsManager:
    app: FastAPI

    _efs_mounted_path: Path
    _project_specific_data_base_directory: str
    _settings: ApplicationSettings

    @classmethod
    async def create(
        cls,
        app: FastAPI,
        efs_mounted_path: Path,
        project_specific_data_base_directory: str,
    ):
        settings = get_application_settings(app)
        return cls(
            app, efs_mounted_path, project_specific_data_base_directory, settings
        )

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
        # Ensure the directory exists with the right parents
        Path.mkdir(_dir_path, parents=True, exist_ok=True)
        # Change the owner to user id 8006(efs) and group id 8106(efs-group)
        os.chown(_dir_path, self._settings.EFS_USER_ID, self._settings.EFS_GROUP_ID)
        # Set directory permissions to allow group write access
        Path.chmod(
            _dir_path, 0o770
        )  # This gives rwx permissions to user and group, and nothing to others
        return _dir_path

    async def get_project_node_data_size(
        self, project_id: ProjectID, node_id: NodeID
    ) -> ByteSize:
        _dir_path = (
            self._efs_mounted_path
            / self._project_specific_data_base_directory
            / f"{project_id}"
            / f"{node_id}"
        )

        service_size = await efs_manager_utils.get_size_bash_async(_dir_path)
        return service_size

    async def remove_project_node_data_write_permissions(
        self, project_id: ProjectID, node_id: NodeID
    ) -> None:
        _dir_path = (
            self._efs_mounted_path
            / self._project_specific_data_base_directory
            / f"{project_id}"
            / f"{node_id}"
        )

        await efs_manager_utils.remove_write_permissions_bash_async(_dir_path)
