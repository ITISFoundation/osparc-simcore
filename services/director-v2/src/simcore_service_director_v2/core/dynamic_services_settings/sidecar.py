import logging
from enum import Enum
from pathlib import Path
from typing import Final

from models_library.basic_types import BootModeEnum, PortInt
from pydantic import Field, NonNegativeInt, PositiveFloat, PositiveInt, validator
from settings_library.base import BaseCustomSettings
from settings_library.r_clone import RCloneSettings as SettingsLibraryRCloneSettings
from settings_library.utils_logging import MixinLoggingSettings
from settings_library.utils_service import DEFAULT_FASTAPI_PORT

from ...constants import DYNAMIC_SIDECAR_DOCKER_IMAGE_RE
from .egress_proxy import EgressProxySettings
from .proxy import DynamicSidecarProxySettings

_logger = logging.getLogger(__name__)

_MINUTE: Final[NonNegativeInt] = 60


class VFSCacheMode(str, Enum):
    __slots__ = ()

    OFF = "off"
    MINIMAL = "minimal"
    WRITES = "writes"
    FULL = "full"


class RCloneSettings(SettingsLibraryRCloneSettings):
    R_CLONE_DIR_CACHE_TIME_SECONDS: PositiveInt = Field(
        10,
        description="time to cache directory entries for",
    )
    R_CLONE_POLL_INTERVAL_SECONDS: PositiveInt = Field(
        9,
        description="time to wait between polling for changes",
    )
    R_CLONE_VFS_CACHE_MODE: VFSCacheMode = Field(
        VFSCacheMode.MINIMAL,  # SEE https://rclone.org/commands/rclone_mount/#vfs-file-caching
        description="VFS operation mode, defines how and when the disk cache is synced",
    )

    @validator("R_CLONE_POLL_INTERVAL_SECONDS")
    @classmethod
    def enforce_r_clone_requirement(cls, v: int, values) -> PositiveInt:
        dir_cache_time = values["R_CLONE_DIR_CACHE_TIME_SECONDS"]
        if v >= dir_cache_time:
            msg = f"R_CLONE_POLL_INTERVAL_SECONDS={v} must be lower than R_CLONE_DIR_CACHE_TIME_SECONDS={dir_cache_time}"
            raise ValueError(msg)
        return v


class DynamicSidecarSettings(BaseCustomSettings, MixinLoggingSettings):
    DYNAMIC_SIDECAR_SC_BOOT_MODE: BootModeEnum = Field(
        ...,
        description="Boot mode used for the dynamic-sidecar services"
        "By defaults, it uses the same boot mode set for the director-v2",
        env=["DYNAMIC_SIDECAR_SC_BOOT_MODE", "SC_BOOT_MODE"],
    )

    DYNAMIC_SIDECAR_LOG_LEVEL: str = Field(
        "WARNING",
        description="log level of the dynamic sidecar"
        "If defined, it captures global env vars LOG_LEVEL and LOGLEVEL from the director-v2 service",
        env=["DYNAMIC_SIDECAR_LOG_LEVEL", "LOG_LEVEL", "LOGLEVEL"],
    )

    DYNAMIC_SIDECAR_IMAGE: str = Field(
        ...,
        regex=DYNAMIC_SIDECAR_DOCKER_IMAGE_RE,
        description="used by the director to start a specific version of the dynamic-sidecar",
    )

    # move to DynamicServicesSettings
    DYNAMIC_SIDECAR_PROXY_SETTINGS: DynamicSidecarProxySettings = Field(
        auto_default_from_env=True
    )

    # move to DynamicServicesSettings
    DYNAMIC_SIDECAR_EGRESS_PROXY_SETTINGS: EgressProxySettings = Field(
        auto_default_from_env=True
    )

    DYNAMIC_SIDECAR_R_CLONE_SETTINGS: RCloneSettings = Field(auto_default_from_env=True)

    #
    # TIMEOUTS AND RETRY dark worlds
    #

    # move to scheduler
    DYNAMIC_SIDECAR_API_REQUEST_TIMEOUT: PositiveFloat = Field(
        15.0,
        description=(
            "the default timeout each request to the dynamic-sidecar API in seconds; as per "
            "design, all requests should answer quite quickly, in theory a few seconds or less"
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_API_CONNECT_TIMEOUT: PositiveFloat = Field(
        5.0,
        description=(
            "Connections to the dynamic-sidecars in the same swarm deployment should be very fast."
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_STARTUP_TIMEOUT_S: PositiveFloat = Field(
        60 * _MINUTE,
        description=(
            "After starting the dynamic-sidecar its docker_node_id is required. "
            "This operation can be slow based on system load, sometimes docker "
            "swarm takes more than seconds to assign the node."
            "Autoscaling of nodes takes time, it is required to wait longer"
            "for nodes to be assigned."
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_API_SAVE_RESTORE_STATE_TIMEOUT: PositiveFloat = Field(
        60.0 * _MINUTE,
        description=(
            "When saving and restoring the state of a dynamic service, depending on the payload "
            "some services take longer or shorter to save and restore. Across the "
            "platform this value is set to 1 hour."
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_API_RESTART_CONTAINERS_TIMEOUT: PositiveFloat = Field(
        1.0 * _MINUTE,
        description=(
            "Restarts all started containers. During this operation, no data "
            "stored in the container will be lost as docker compose restart "
            "will not alter the state of the files on the disk nor its environment."
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_WAIT_FOR_CONTAINERS_TO_START: PositiveFloat = Field(
        60.0 * _MINUTE,
        description=(
            "When starting container (`docker compose up`), images might "
            "require pulling before containers are started."
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_WAIT_FOR_SERVICE_TO_STOP: PositiveFloat = Field(
        60.0 * _MINUTE,
        description=(
            "When stopping a service, depending on the amount of data to store, "
            "the operation might be very long. Also all relative created resources: "
            "services, containsers, volumes and networks need to be removed. "
        ),
    )

    # move to scheduler
    DYNAMIC_SIDECAR_PROJECT_NETWORKS_ATTACH_DETACH_S: PositiveFloat = Field(
        3.0 * _MINUTE,
        description=(
            "timeout for attaching/detaching project networks to/from a container"
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_VOLUMES_REMOVAL_TIMEOUT_S: PositiveFloat = Field(
        1.0 * _MINUTE,
        description=(
            "time to wait before giving up on removing dynamic-sidecar's volumes"
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_STATUS_API_TIMEOUT_S: PositiveFloat = Field(
        1.0,
        description=(
            "when requesting the status of a service this is the "
            "maximum amount of time the request can last"
        ),
    )

    # move to scheduler
    DYNAMIC_SIDECAR_CLIENT_REQUEST_TIMEOUT_S: PositiveFloat = Field(
        1 * _MINUTE,
        description=(
            "Connectivity between director-v2 and a dy-sidecar can be "
            "temporarily disrupted if network between swarm nodes has "
            "issues. To avoid the sidecar being marked as failed, "
            "allow for some time to pass before declaring it failed."
        ),
    )

    #
    # DEVELOPMENT ONLY config
    #

    DYNAMIC_SIDECAR_MOUNT_PATH_DEV: Path | None = Field(
        None,
        description="Host path to the dynamic-sidecar project. Used as source path to mount to the dynamic-sidecar [DEVELOPMENT ONLY]",
        example="osparc-simcore/services/dynamic-sidecar",
    )

    DYNAMIC_SIDECAR_PORT: PortInt = Field(
        DEFAULT_FASTAPI_PORT,
        description="port on which the webserver for the dynamic-sidecar is exposed [DEVELOPMENT ONLY]",
    )

    DYNAMIC_SIDECAR_EXPOSE_PORT: bool = Field(
        default=False,
        description="Publishes the service on localhost for debuging and testing [DEVELOPMENT ONLY]"
        "Can be used to access swagger doc from the host as http://127.0.0.1:30023/dev/doc "
        "where 30023 is the host published port",
    )

    # move to scheduler
    DYNAMIC_SIDECAR_DOCKER_NODE_RESOURCE_LIMITS_ENABLED: bool = Field(
        default=False,
        description=(
            "Limits concurrent service saves for a docker node. Guarantees "
            "that no more than X services use a resource together. "
            "NOTE: A node can end up with all the services from a single study. "
            "When the study is closed/opened all the services will try to "
            "upload/download their data. This causes a lot of disk "
            "and network stress (especially for low power nodes like in AWS). "
            "Some nodes collapse under load or behave unexpectedly."
        ),
    )
    # move to scheduler
    DYNAMIC_SIDECAR_DOCKER_NODE_CONCURRENT_RESOURCE_SLOTS: PositiveInt = Field(
        2, description="Amount of slots per resource on a node"
    )
    # move to scheduler
    DYNAMIC_SIDECAR_DOCKER_NODE_SAVES_LOCK_TIMEOUT_S: PositiveFloat = Field(
        10,
        description=(
            "Lifetime of the lock. Allows the system to recover a lock "
            "in case of crash, the lock will expire and result as released."
        ),
    )

    @validator("DYNAMIC_SIDECAR_MOUNT_PATH_DEV", pre=True)
    @classmethod
    def auto_disable_if_production(cls, v, values):
        if v and values.get("DYNAMIC_SIDECAR_SC_BOOT_MODE") == BootModeEnum.PRODUCTION:
            _logger.warning(
                "In production DYNAMIC_SIDECAR_MOUNT_PATH_DEV cannot be set to %s, enforcing None",
                v,
            )
            return None
        return v

    @validator("DYNAMIC_SIDECAR_EXPOSE_PORT", pre=True, always=True)
    @classmethod
    def auto_enable_if_development(cls, v, values):
        if (
            boot_mode := values.get("DYNAMIC_SIDECAR_SC_BOOT_MODE")
        ) and boot_mode.is_devel_mode():
            # Can be used to access swagger doc from the host as http://127.0.0.1:30023/dev/doc
            return True
        return v

    @validator("DYNAMIC_SIDECAR_IMAGE", pre=True)
    @classmethod
    def strip_leading_slashes(cls, v: str) -> str:
        return v.lstrip("/")

    @validator("DYNAMIC_SIDECAR_LOG_LEVEL")
    @classmethod
    def _validate_log_level(cls, value) -> str:
        log_level: str = cls.validate_log_level(value)
        return log_level
