import os
from pathlib import Path
from typing import Any

from models_library.api_schemas_directorv2.services import (
    CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import RunID
from models_library.users import UserID
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from settings_library.efs import (
    NFS_PROTOCOL,
    NFS_REQUEST_TIMEOUT,
    NUMBER_OF_RETRANSMISSIONS,
    PORT_MODE,
    READ_SIZE,
    RECOVERY_MODE,
    WRITE_SIZE,
    AwsEfsSettings,
)
from settings_library.r_clone import S3Provider

from ...core.dynamic_services_settings.sidecar import RCloneSettings
from .errors import DynamicSidecarError

DY_SIDECAR_SHARED_STORE_PATH = Path("/shared-store")


def _get_s3_volume_driver_config(
    r_clone_settings: RCloneSettings,
    project_id: ProjectID,
    node_uuid: NodeID,
    storage_directory_name: str,
) -> dict[str, Any]:
    assert "/" not in storage_directory_name  # nosec
    driver_config: dict[str, Any] = {
        "Name": "rclone",
        "Options": {
            "type": "s3",
            "s3-access_key_id": r_clone_settings.R_CLONE_S3.S3_ACCESS_KEY,
            "s3-secret_access_key": r_clone_settings.R_CLONE_S3.S3_SECRET_KEY,
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
    if r_clone_settings.R_CLONE_S3.S3_ENDPOINT:
        driver_config["Options"][
            "s3-endpoint"
        ] = r_clone_settings.R_CLONE_S3.S3_ENDPOINT

    extra_options: dict[str, str] | None = None

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
            "s3-region": r_clone_settings.R_CLONE_S3.S3_REGION,
            "s3-acl": "private",
        }
    else:
        msg = f"Unexpected, all {S3Provider.__name__} should be covered"
        raise DynamicSidecarError(msg=msg)

    assert extra_options is not None  # nosec
    options: dict[str, Any] = driver_config["Options"]
    options.update(extra_options)

    return driver_config


def _get_efs_volume_driver_config(
    efs_settings: AwsEfsSettings,
    project_id: ProjectID,
    node_uuid: NodeID,
    storage_directory_name: str,
) -> dict[str, Any]:
    assert "/" not in storage_directory_name  # nosec
    driver_config: dict[str, Any] = {
        "Options": {
            "type": "nfs",
            "o": f"addr={efs_settings.EFS_DNS_NAME},rw,nfsvers={NFS_PROTOCOL},rsize={READ_SIZE},wsize={WRITE_SIZE},{RECOVERY_MODE},timeo={NFS_REQUEST_TIMEOUT},retrans={NUMBER_OF_RETRANSMISSIONS},{PORT_MODE}",
            "device": f":/{efs_settings.EFS_PROJECT_SPECIFIC_DATA_DIRECTORY}/{project_id}/{node_uuid}/{storage_directory_name}",
        },
    }
    return driver_config


class DynamicSidecarVolumesPathsResolver:
    BASE_PATH: Path = Path("/dy-volumes")

    @classmethod
    def target(cls, path: Path) -> str:
        """Returns a folder path within `/dy-volumes` folder"""
        target_path = cls.BASE_PATH / path.relative_to("/")
        return f"{target_path}"

    @classmethod
    def volume_name(cls, path: Path) -> str:
        """Returns a volume name created from path. There is not possibility to go back to the original path from the volume name"""
        return f"{path}".replace(os.sep, "_")

    @classmethod
    def source(cls, path: Path, node_uuid: NodeID, run_id: RunID) -> str:
        """Returns a valid and unique volume name that is composed out of identifiers, namely
            - relative target path
            - node_uuid
            - run_id

        Guarantees that the volume name is unique between runs while also
        taking into consideration the limit for the volume name's length
        (255 characters).

        SEE examples in `tests/unit/test_modules_dynamic_sidecar_volumes_resolver.py`
        """
        # NOTE: issues can occur when the paths of the mounted outputs, inputs
        # and state folders are very long and share the same subdirectory path.
        # Reversing volume name to prevent these issues from happening.
        reversed_volume_name = cls.volume_name(path)[::-1]

        # ensure prefix size does not change
        prefix = f"{PREFIX_DYNAMIC_SIDECAR_VOLUMES}_{run_id}_{node_uuid}"
        assert len(prefix) == CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME - 1  # nosec

        unique_name = f"{prefix}_{reversed_volume_name}"
        return unique_name[:255]

    @classmethod
    def mount_entry(
        cls,
        swarm_stack_name: str,
        path: Path,
        node_uuid: NodeID,
        run_id: RunID,
        project_id: ProjectID,
        user_id: UserID,
        volume_size_limit: str | None,
    ) -> dict[str, Any]:
        """
        Creates specification for mount to be added to containers created as part of a service
        """
        return {
            "Source": cls.source(path, node_uuid, run_id),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "source": cls.source(path, node_uuid, run_id),
                    "run_id": f"{run_id}",
                    "node_uuid": f"{node_uuid}",
                    "study_id": f"{project_id}",
                    "user_id": f"{user_id}",
                    "swarm_stack_name": swarm_stack_name,
                },
                "DriverConfig": (
                    {"Options": {"size": volume_size_limit}}
                    if volume_size_limit is not None
                    else None
                ),
            },
        }

    @classmethod
    def mount_shared_store(
        cls,
        run_id: RunID,
        node_uuid: NodeID,
        project_id: ProjectID,
        user_id: UserID,
        swarm_stack_name: str,
        *,
        has_quota_support: bool,
    ) -> dict[str, Any]:
        return cls.mount_entry(
            swarm_stack_name=swarm_stack_name,
            path=DY_SIDECAR_SHARED_STORE_PATH,
            node_uuid=node_uuid,
            run_id=run_id,
            project_id=project_id,
            user_id=user_id,
            volume_size_limit="1M" if has_quota_support else None,
        )

    @classmethod
    def mount_user_preferences(
        cls,
        user_preferences_path: Path,
        run_id: RunID,
        node_uuid: NodeID,
        project_id: ProjectID,
        user_id: UserID,
        swarm_stack_name: str,
        *,
        has_quota_support: bool,
    ):
        return cls.mount_entry(
            swarm_stack_name=swarm_stack_name,
            path=user_preferences_path,
            node_uuid=node_uuid,
            run_id=run_id,
            project_id=project_id,
            user_id=user_id,
            # NOTE: the contents of this volume will be zipped and much
            # be at most `_MAX_PREFERENCES_TOTAL_SIZE`, this 10M accounts
            # for files and data that can be compressed a lot
            volume_size_limit="10M" if has_quota_support else None,
        )

    @classmethod
    def mount_r_clone(
        cls,
        swarm_stack_name: str,
        path: Path,
        node_uuid: NodeID,
        run_id: RunID,
        project_id: ProjectID,
        user_id: UserID,
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
                    "node_uuid": f"{node_uuid}",
                    "study_id": f"{project_id}",
                    "user_id": f"{user_id}",
                    "swarm_stack_name": swarm_stack_name,
                },
                "DriverConfig": _get_s3_volume_driver_config(
                    r_clone_settings=r_clone_settings,
                    project_id=project_id,
                    node_uuid=node_uuid,
                    storage_directory_name=cls.volume_name(path).strip("_"),
                ),
            },
        }

    @classmethod
    def mount_efs(
        cls,
        swarm_stack_name: str,
        path: Path,
        node_uuid: NodeID,
        run_id: RunID,
        project_id: ProjectID,
        user_id: UserID,
        efs_settings: AwsEfsSettings,
        storage_directory_name: str,
    ) -> dict[str, Any]:
        return {
            "Source": cls.source(path, node_uuid, run_id),
            "Target": cls.target(path),
            "Type": "volume",
            "VolumeOptions": {
                "Labels": {
                    "source": cls.source(path, node_uuid, run_id),
                    "run_id": f"{run_id}",
                    "node_uuid": f"{node_uuid}",
                    "study_id": f"{project_id}",
                    "user_id": f"{user_id}",
                    "swarm_stack_name": swarm_stack_name,
                },
                "DriverConfig": _get_efs_volume_driver_config(
                    efs_settings=efs_settings,
                    project_id=project_id,
                    node_uuid=node_uuid,
                    storage_directory_name=storage_directory_name,
                ),
            },
        }
