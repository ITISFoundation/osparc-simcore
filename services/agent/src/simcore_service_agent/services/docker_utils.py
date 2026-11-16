import logging
from collections.abc import Iterator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Final

from aiodocker import DockerError
from aiodocker.docker import Docker
from aiodocker.volumes import DockerVolume
from common_library.logging.logging_errors import create_troubleshooting_log_kwargs
from fastapi import FastAPI
from models_library.api_schemas_directorv2.services import (
    CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME,
)
from servicelib.docker_constants import PREFIX_DYNAMIC_SIDECAR_VOLUMES
from servicelib.logging_utils import log_catch, log_context
from servicelib.r_clone_utils import get_r_clone_version
from starlette import status

from ..core.settings import ApplicationSettings
from ..models.volumes import VolumeDetails, VolumeDetailsAdapter
from .backup import backup_volume
from .instrumentation import get_instrumentation

_logger = logging.getLogger(__name__)

_STALE_MOUNTPOINT_ERROR_SUBSTRS: Final[tuple[str, ...]] = (
    "transport endpoint is not connected",
    "device or resource busy",
)


def _reverse_string(to_reverse: str) -> str:
    return to_reverse[::-1]


def _is_stale_mountpoint_error(exc: DockerError) -> bool:
    error_text = str(exc).lower()
    return any(sub in error_text for sub in _STALE_MOUNTPOINT_ERROR_SUBSTRS)


_EXCLUDE_VOLUMES: Final[tuple[str, ...]] = (
    _reverse_string("inputs"),
    _reverse_string("shared-store"),
    _reverse_string("traces"),
)


def _does_volume_require_backup(volume_name: str) -> bool:
    # from    `dyv_1726228407_891aa1a7-eb31-459f-8aed-8c902f5f5fb0_dd84f39e-7154-4a13-ba1d-50068d723104_stupni_www_`
    # returns `stupni_www_`
    inverse_name_part = volume_name[CHARS_IN_VOLUME_NAME_BEFORE_DIR_NAME:]
    return not inverse_name_part.startswith(_EXCLUDE_VOLUMES)


async def get_unused_dynamic_sidecar_volumes(docker: Docker) -> set[str]:
    """Returns all dynamic-sidecar volumes not referenced by any container"""
    volumes = await docker.volumes.list()
    volume_infos: list[dict] = volumes["Volumes"] or []
    all_volumes: set[str] = {volume["Name"] for volume in volume_infos}
    volume_names_by_mountpoint: dict[str, str] = {
        str(Path(volume["Mountpoint"])): volume["Name"] for volume in volume_infos if volume.get("Mountpoint")
    }

    containers = await docker.containers.list(all=True)

    used_volumes: set[str] = set()
    for container in containers:
        container_info = await container.show()
        mounts = container_info.get("Mounts", [])
        container_is_running = container_info.get("State", {}).get("Running", False)
        for mount in mounts:
            if mount["Type"] == "volume":
                used_volumes.add(mount["Name"])
            # rclone mount containers (rcm-*) bind the volume mountpoint; exited ones hold no mount
            elif (
                container_is_running
                and mount["Type"] == "bind"
                and (volume_name := volume_names_by_mountpoint.get(str(Path(mount["Source"]))))
            ):
                used_volumes.add(volume_name)

    unused_volumes = all_volumes - used_volumes
    return {v for v in unused_volumes if v.startswith(PREFIX_DYNAMIC_SIDECAR_VOLUMES)}


async def get_volume_details(docker: Docker, *, volume_name: str) -> VolumeDetails:
    volume_details = await DockerVolume(docker, volume_name).show()
    return VolumeDetailsAdapter.validate_python(volume_details)


@contextmanager
def _log_volume_not_found(volume_name: str) -> Iterator[None]:
    try:
        yield
    except DockerError as e:
        if e.status == status.HTTP_404_NOT_FOUND:
            _logger.info("Volume not found '%s'", volume_name)
        else:
            raise


async def _backup_volume(app: FastAPI, docker: Docker, *, volume_name: str) -> None:
    """Backs up only volumes which require a backup"""
    if _does_volume_require_backup(volume_name):
        with log_context(_logger, logging.INFO, f"backup '{volume_name}'"):
            volume_details = await get_volume_details(docker, volume_name=volume_name)
            settings: ApplicationSettings = app.state.settings
            get_instrumentation(app).agent_metrics.backedup_volumes(settings.AGENT_DOCKER_NODE_ID)
            await backup_volume(app, volume_details, volume_name)
    else:
        _logger.debug("No backup is required for '%s'", volume_name)


async def _volume_mountpoint_is_held_by_running_container(docker: Docker, mountpoint: Path) -> bool:
    """True when a running container binds the mountpoint, so the mount is live not stale"""
    mountpoint_path = Path(mountpoint)
    containers = await docker.containers.list(all=False)
    for container in containers:
        container_info = await container.show()
        for mount in container_info.get("Mounts", []):
            if (
                mount["Type"] == "bind"
                and Path(mount["Source"]).is_relative_to(mountpoint_path)
                and container_info.get("State", {}).get("Running", False)
            ):
                return True
    return False


async def _resolve_mountpoint(volume: DockerVolume) -> Path | None:
    try:
        volume_info = await volume.show()
        mountpoint_str = volume_info.get("Mountpoint")
        return Path(mountpoint_str) if mountpoint_str else None
    except DockerError as show_err:
        if show_err.status == status.HTTP_404_NOT_FOUND:
            raise
        return None


async def _lazy_unmount_stale_mountpoint(
    docker: Docker, volume: DockerVolume, *, volume_name: str, err: DockerError
) -> tuple[Path | None, bool]:
    """Resolves the volume mountpoint and lazy-unmounts it; returns (mountpoint, attempted)"""
    mountpoint = await _resolve_mountpoint(volume)
    if mountpoint is None:
        return None, False

    # a running binder means the volume went live again; unmount propagates via rshared and kills its mount
    if await _volume_mountpoint_is_held_by_running_container(docker, mountpoint):
        msg = f"volume '{volume_name}' mountpoint held by a running container, refusing lazy unmount"
        raise DockerError(status.HTTP_409_CONFLICT, msg) from err

    with log_context(
        _logger,
        logging.INFO,
        f"lazy unmount of stale mountpoint '{mountpoint}' for volume '{volume_name}'",
    ):
        await _try_lazy_unmount(docker, mountpoint)

    # a mount may attach between probe and unmount; re-check blocks force-delete under a live service
    if await _volume_mountpoint_is_held_by_running_container(docker, mountpoint):
        msg = f"volume '{volume_name}' mountpoint attached by a running container after lazy unmount, refusing delete"
        raise DockerError(status.HTTP_409_CONFLICT, msg) from err

    return mountpoint, True


async def remove_volume(app: FastAPI, docker: Docker, *, volume_name: str, requires_backup: bool) -> None:
    """Removes a volume and backs data up if required"""
    with (
        log_context(_logger, logging.DEBUG, f"removing '{volume_name}'"),
        log_catch(_logger, reraise=False),
        _log_volume_not_found(volume_name),
    ):
        if requires_backup:
            await _backup_volume(app, docker, volume_name=volume_name)

        settings: ApplicationSettings = app.state.settings
        get_instrumentation(app).agent_metrics.remove_volumes(settings.AGENT_DOCKER_NODE_ID)

        volume = DockerVolume(docker, volume_name)

        try:
            await volume.delete()
        except DockerError as err:
            if err.status == status.HTTP_404_NOT_FOUND:
                raise

            if not _is_stale_mountpoint_error(err):
                raise

            # NOTE: This happens on hosts with stale FUSE mountpoints under the
            # docker volumes directory (e.g. after abrupt shutdowns). Docker may
            # fail volume deletion while trying to `lstat` the mountpoint.
            _logger.info(
                "Failed to remove volume '%s' due to stale mountpoint; attempting lazy unmount and retry",
                volume_name,
            )

            mountpoint, lazy_unmount_attempted = await _lazy_unmount_stale_mountpoint(
                docker, volume, volume_name=volume_name, err=err
            )

            try:
                await volume.delete(force=True)
            except DockerError as retry_err:
                if lazy_unmount_attempted and _is_stale_mountpoint_error(retry_err):
                    _logger.warning(
                        **create_troubleshooting_log_kwargs(
                            f"Volume '{volume_name}' is still busy after lazy unmount",
                            error=retry_err,
                            error_context={"mountpoint": f"{mountpoint}"},
                            tip=f"run 'umount -l {mountpoint}' on the host",
                        )
                    )
                    return
                raise

        get_instrumentation(app).agent_metrics.remove_volumes(settings.AGENT_DOCKER_NODE_ID)


def _find_volumes_root(path: Path) -> Path:
    # path =  /mnt/sdb1/volumes/volume_name...
    parts = path.parts
    first_occurrence = parts.index("volumes")
    return Path(*parts[: first_occurrence + 1])


async def _try_lazy_unmount(docker: Docker, mountpoint: Path) -> None:
    volumes_root = _find_volumes_root(mountpoint)

    r_clone_version = await get_r_clone_version()

    container = await docker.containers.run(
        config={
            "Image": f"rclone/rclone:{r_clone_version}",
            "Entrypoint": ["sh", "-c", f"fusermount3 -uz {mountpoint}"],
            "HostConfig": {
                "AutoRemove": True,
                "CapAdd": ["SYS_ADMIN"],
                "Devices": [
                    {
                        "PathOnHost": "/dev/fuse",
                        "PathInContainer": "/dev/fuse",
                        "CgroupPermissions": "rwm",
                    }
                ],
                "SecurityOpt": ["apparmor:unconfined"],
                "Binds": [
                    f"{volumes_root}:{volumes_root}:rshared",
                ],
            },
        }
    )

    # Wait for container to stop and get its exit status
    result = await container.wait()
    status_code = result.get("StatusCode", 1)

    if status_code != 0:
        logs = await container.log(stdout=True, stderr=True)
        msg = f"rclone helper failed (exit {status_code}):\n{''.join(logs)}"
        raise RuntimeError(msg)


async def get_containers_with_prefixes(docker: Docker, prefixes: set[str]) -> set[str]:
    """Returns a set of container names matching any of the given prefixes"""
    filtered_containers = await docker.containers.list(all=True, filters={"name": list(prefixes)})

    result: set[str] = set()

    for container in filtered_containers:
        for name in container["Names"]:
            container_name = name.lstrip("/")
            if any(container_name.startswith(prefix) for prefix in prefixes):
                result.add(container_name)

    return result


async def remove_container_forcefully(docker: Docker, container_id: str, *, stop_before_removal: bool) -> None:
    """Removes a container regardless of it's state"""
    try:
        container = await docker.containers.get(container_id)
        if stop_before_removal:
            with (
                suppress(DockerError),
                log_context(_logger, logging.DEBUG, f"stopping container '{container_id}'"),
            ):
                await container.stop()

        await container.delete(force=True)
    except DockerError as e:
        if e.status != status.HTTP_404_NOT_FOUND:
            raise
