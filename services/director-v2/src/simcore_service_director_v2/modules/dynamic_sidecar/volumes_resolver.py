import os
from pathlib import Path
from typing import Any
from uuid import UUID

from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from settings_library.r_clone import S3Provider

from ...core.settings import RCloneSettings
from ...models.schemas.constants import DY_SIDECAR_NAMED_VOLUME_PREFIX
from .errors import DynamicSidecarError

DY_SIDECAR_SHARED_STORE_PATH = Path("/shared-store")


def _get_s3_volume_driver_config(
    r_clone_settings: RCloneSettings,
    project_id: ProjectID,
    node_uuid: NodeID,
    storage_directory_name: str,
) -> dict[str, Any]:
    assert "/" not in storage_directory_name  # no sec
    driver_config = {
        "Name": "rclone",
        "Options": {
            "type": "s3",
            "s3-access_key_id": r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
            "s3-secret_access_key": r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
            "s3-endpoint": r_clone_settings.R_CLONE_S3.S3_ENDPOINT,
            "path": f"{r_clone_settings.R_CLONE_S3.S3_BUCKET_NAME}/{project_id}/{node_uuid}/{storage_directory_name}",
            "allow-other": "true",
            "vfs-cache-mode": r_clone_settings.R_CLONE_VFS_CACHE_MODE.value,
            # Directly connected to how much time it takes for
            # files to appear on remote s3, please se discussion
            # SEE https://forum.rclone.org/t/file-added-to-s3-on-one-machine-not-visible-on-2nd-machine-unless-mount-is-restarted/20645
            # SEE https://rclone.org/commands/rclone_mount/#vfs-directory-cache
            "dir-cache-time": f"{r_clone_settings.R_CLONE_DIR_CACHE_TIME_SECONDS}s",
            "poll-interval": f"{r_clone_settings.R_CLONE_POLL_INTERVAL_SECONDS}s",
        },
    }

    extra_options = None

    if r_clone_settings.R_CLONE_PROVIDER == S3Provider.MINIO:
        extra_options = {
            "s3-provider": "Minio",
            "s3-region": "us-east-1",
            "s3-location_constraint": "",
            "s3-server_side_encryption": "",
        }
    elif r_clone_settings.R_CLONE_PROVIDER == S3Provider.CEPH:
        extra_options = {
            "s3-provider": "Ceph",
            "s3-acl": "private",
        }
    elif r_clone_settings.R_CLONE_PROVIDER == S3Provider.AWS:
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
    def source(cls, path: Path, node_uuid: NodeID, run_id: UUID) -> str:
        """
        Put together a uniquely identified name for the volume being mounted.
        The most important requirement is that it is guaranteed to be unique
        between runs and

        Example:
        Given:
        - path="/this/is/a/data/folder"
        - node_uuid="17f5b46d-505c-489e-9818-f6d294c892d9"
        - run_id="17f5b46d-505c-489e-9818-f6d294c892d9"

        The below name will be generated:
        `dyv_17f5b46d-505c-489e-9818-f6d294c892d9_this_is_a_data_folder_17f5b46d-505c-489e-9818-f6d294c892d9`
        """
        # NOTE: volume name is capped at 255 characters
        # NOTE: it is OK for parts of the node_uuid or of the volume name to be
        # removed. This unique_name is only used for volume removal. The
        # dynamic-sidecar uses the labels to correctly identify the volume.
        # NOTE: issues can occur when the paths of the mounted outputs, inputs
        # and state folders are very long and share the same subdirectory path
        # Generally this should not be an issue.
        full_unique_name = f"{DY_SIDECAR_NAMED_VOLUME_PREFIX}_{run_id}{cls._volume_name(path)}_{node_uuid}"
        return full_unique_name[:255]

    @classmethod
    def mount_entry(
        cls, swarm_stack_name: str, path: Path, node_uuid: NodeID, run_id: UUID
    ) -> dict[str, Any]:
        """
        mounts local directories form the host where the service
        dynamic-sidecar) is running.
        """
        return {
            "Source": cls.source(path, node_uuid, run_id),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "source": cls.source(path, node_uuid, run_id),
                    "run_id": f"{run_id}",
                    "uuid": f"{node_uuid}",
                    "swarm_stack_name": swarm_stack_name,
                }
            },
        }

    @classmethod
    def mount_shared_store(
        cls, swarm_stack_name: str, node_uuid: NodeID, run_id: UUID
    ) -> dict[str, Any]:
        return {
            "Source": cls.source(DY_SIDECAR_SHARED_STORE_PATH, node_uuid, run_id),
            "Target": cls.target(DY_SIDECAR_SHARED_STORE_PATH),
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "source": cls.source(
                        DY_SIDECAR_SHARED_STORE_PATH, node_uuid, run_id
                    ),
                    "run_id": f"{run_id}",
                    "uuid": f"{node_uuid}",
                    "swarm_stack_name": swarm_stack_name,
                }
            },
        }

    @classmethod
    def mount_r_clone(
        cls,
        swarm_stack_name: str,
        path: Path,
        project_id: ProjectID,
        node_uuid: NodeID,
        run_id: UUID,
        r_clone_settings: RCloneSettings,
    ) -> dict[str, Any]:
        return {
            "Source": cls.source(path, node_uuid, run_id),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "source": cls.source(path, node_uuid, run_id),
                    "run_id": f"{run_id}",
                    "uuid": f"{node_uuid}",
                    "swarm_stack_name": swarm_stack_name,
                },
                "DriverConfig": _get_s3_volume_driver_config(
                    r_clone_settings=r_clone_settings,
                    project_id=project_id,
                    node_uuid=node_uuid,
                    storage_directory_name=cls._volume_name(path).strip("_"),
                ),
            },
        }
