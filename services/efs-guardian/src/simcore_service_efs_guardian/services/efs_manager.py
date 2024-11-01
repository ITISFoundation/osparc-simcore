import logging
import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from pydantic import ByteSize, TypeAdapter, ValidationError

from ..core.settings import ApplicationSettings, get_application_settings
from . import efs_manager_utils

_logger = logging.getLogger(__name__)


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

    async def check_project_node_data_directory_exits(
        self, project_id: ProjectID, node_id: NodeID
    ) -> bool:
        _dir_path = (
            self._efs_mounted_path
            / self._project_specific_data_base_directory
            / f"{project_id}"
            / f"{node_id}"
        )

        return _dir_path.exists()

    async def get_project_node_data_size(
        self, project_id: ProjectID, node_id: NodeID
    ) -> ByteSize:
        _dir_path = (
            self._efs_mounted_path
            / self._project_specific_data_base_directory
            / f"{project_id}"
            / f"{node_id}"
        )

        return await efs_manager_utils.get_size_bash_async(_dir_path)

    async def list_project_node_state_names(
        self, project_id: ProjectID, node_id: NodeID
    ) -> list[str]:
        """
        These are currently state volumes that are mounted via docker volume to dynamic sidecar and user services
        (ex. ".data_assets" and "home_user_workspace")
        """
        _dir_path = (
            self._efs_mounted_path
            / self._project_specific_data_base_directory
            / f"{project_id}"
            / f"{node_id}"
        )

        project_node_states = []
        for child in _dir_path.iterdir():
            if child.is_dir():
                project_node_states.append(child.name)
            else:
                _logger.error(
                    "This is not a directory. This should not happen! %s",
                    _dir_path / child.name,
                )
        return project_node_states

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

    async def list_projects_across_whole_efs(self) -> list[ProjectID]:
        _dir_path = self._efs_mounted_path / self._project_specific_data_base_directory

        # Filter and list only directories (which should be Project UUIDs)
        project_uuids = []
        for child in _dir_path.iterdir():
            if child.is_dir():
                try:
                    _project_id = TypeAdapter(ProjectID).validate_python(child.name)
                    project_uuids.append(_project_id)
                except ValidationError:
                    _logger.error(
                        "This is not a project ID. This should not happen! %s",
                        _dir_path / child.name,
                    )
            else:
                _logger.error(
                    "This is not a directory. This should not happen! %s",
                    _dir_path / child.name,
                )

        return project_uuids

    async def remove_project_efs_data(self, project_id: ProjectID) -> None:
        _dir_path = (
            self._efs_mounted_path
            / self._project_specific_data_base_directory
            / f"{project_id}"
        )

        if Path.exists(_dir_path):
            # Remove the directory and all its contents
            try:
                shutil.rmtree(_dir_path)
                _logger.info("%s has been deleted.", _dir_path)
            except FileNotFoundError:
                _logger.exception("Directory %s does not exist.", _dir_path)
            except PermissionError:
                _logger.exception(
                    "Permission denied when trying to delete %s.", _dir_path
                )
            except NotADirectoryError:
                _logger.exception("%s is not a directory.", _dir_path)
            except OSError:
                _logger.exception("Issue with path: %s", _dir_path)
        else:
            _logger.error("%s does not exist.", _dir_path)
