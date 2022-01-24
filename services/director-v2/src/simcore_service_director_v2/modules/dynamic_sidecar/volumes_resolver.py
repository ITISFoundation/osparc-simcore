import os
from pathlib import Path
from typing import Any, Dict

from settings_library.rclone import RCloneSettings
from models_library.projects_nodes_io import NodeID
from models_library.projects import ProjectID


class DynamicSidecarVolumesPathsResolver:
    BASE_PATH: Path = Path("/dy-volumes")

    @classmethod
    def target(cls, path: Path) -> str:
        """returns path relative to `/dy-volumes`"""
        target_path = cls.BASE_PATH / path.relative_to("/")
        return f"{target_path}"

    @classmethod
    def _source(cls, compose_namespace: str, path: Path) -> str:
        volume_name = f"{path}".replace(os.sep, "_")
        return f"{compose_namespace}{volume_name}"

    @classmethod
    def mount_entry(
        cls, compose_namespace: str, path: Path, node_uuid: NodeID
    ) -> Dict[str, Any]:
        #   # TODO: migrate this to path resolver to be mounted
        #   the volume is created here by the docker engine

        # mounts local directories form the host where the service
        # (dynamic-sidecar) is running.
        return {
            "Source": cls._source(compose_namespace, path),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {"Labels": {"uuid": f"{node_uuid}"}},
        }

    @classmethod
    def mount_r_clone(
        cls,
        compose_namespace: str,
        path: Path,
        project_id: ProjectID,
        node_uuid: NodeID,
        # TODO: use r_clone settings to pull in information about the endpoint
        # r_clone_settings: RCloneSettings,
    ) -> Dict[str, Any]:

        return {
            "Source": cls._source(compose_namespace, path),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "uuid": f"{node_uuid}",
                },
                "DriverConfig": {
                    "Name": "rclone",
                    "Options": {
                        "type": "s3",
                        "s3-provider": "Minio",
                        "s3-env_auth": "false",
                        "s3-access_key_id": "12345678",
                        "s3-secret_access_key": "12345678",
                        "s3-region": "us-east-1",
                        "s3-endpoint": "http://172.17.0.1:9001",
                        "s3-location_constraint": "",
                        "s3-server_side_encryption": "",
                        # TODO: PC, SAN this "simcore" where is it defined, can I use a constant
                        "path": f"simcore/{project_id}/{node_uuid}",
                        "allow-other": "true",
                    },
                },
            },
        }
