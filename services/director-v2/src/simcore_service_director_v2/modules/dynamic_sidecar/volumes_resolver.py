import os
from pathlib import Path
from typing import Any, Dict

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID

from ...core.settings import RCloneSettings, S3Provider
from .errors import DynamicSidecarError


def _get_s3_volume_driver_config(
    r_clone_settings: RCloneSettings,
    project_id: ProjectID,
    node_uuid: NodeID,
    storage_directory_name: str,
) -> Dict[str, Any]:
    assert "/" not in storage_directory_name  # no sec
    driver_config = {
        "Name": "rclone",
        "Options": {
            "type": "s3",
            "s3-access_key_id": r_clone_settings.S3_ACCESS_KEY,
            "s3-secret_access_key": r_clone_settings.S3_SECRET_KEY,
            "s3-endpoint": r_clone_settings.endpoint,
            "path": f"{r_clone_settings.S3_BUCKET_NAME}/{project_id}/{node_uuid}/{storage_directory_name}",
            "allow-other": "true",
            "vfs-cache-mode": "full",
            # Directly connected to how much time it takes for
            # files to appear on remote s3, please se discussion
            # SEE https://forum.rclone.org/t/file-added-to-s3-on-one-machine-not-visible-on-2nd-machine-unless-mount-is-restarted/20645
            "dir-cache-time": "10s",
        },
    }

    extra_options = None

    if r_clone_settings.S3_PROVIDER == S3Provider.MINIO:
        extra_options = {
            "s3-provider": "Minio",
            "s3-region": "us-east-1",
            "s3-location_constraint": "",
            "s3-server_side_encryption": "",
        }
    elif r_clone_settings.S3_PROVIDER == S3Provider.CEPH:
        extra_options = {
            "s3-provider": "Ceph",
            "s3-acl": "private",
        }
    elif r_clone_settings.S3_PROVIDER == S3Provider.AWS:
        extra_options = {
            "s3-provider": "AWS",
            "s3-region": "us-east-1",
            "s3-acl": "private",
        }
    else:
        raise DynamicSidecarError(
            f"Unexpected, all {S3Provider.__name__} should be covered"
        )

    assert extra_options is not None  # no sec
    driver_config["Options"].update(extra_options)

    return driver_config


class DynamicSidecarVolumesPathsResolver:
    BASE_PATH: Path = Path("/dy-volumes")

    @classmethod
    def target(cls, path: Path) -> str:
        """returns path relative to `/dy-volumes`"""
        target_path = cls.BASE_PATH / path.relative_to("/")
        return f"{target_path}"

    @classmethod
    def _volume_name(cls, path: Path) -> str:
        return f"{path}".replace(os.sep, "_")

    @classmethod
    def _source(cls, compose_namespace: str, path: Path) -> str:
        return f"{compose_namespace}{cls._volume_name(path)}"

    @classmethod
    def mount_entry(
        cls, compose_namespace: str, path: Path, node_uuid: NodeID
    ) -> Dict[str, Any]:
        """
        mounts local directories form the host where the service
        dynamic-sidecar) is running.
        """
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
        r_clone_settings: RCloneSettings,
    ) -> Dict[str, Any]:
        return {
            "Source": cls._source(compose_namespace, path),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "uuid": f"{node_uuid}",
                },
                "DriverConfig": _get_s3_volume_driver_config(
                    r_clone_settings=r_clone_settings,
                    project_id=project_id,
                    node_uuid=node_uuid,
                    storage_directory_name=cls._volume_name(path).strip("_"),
                ),
            },
        }
