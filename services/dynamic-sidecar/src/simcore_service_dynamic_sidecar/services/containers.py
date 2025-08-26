import logging

from fastapi import FastAPI

from ..core.settings import ApplicationSettings
from ..core.validation import ComposeSpecValidation, get_and_validate_compose_spec
from ..models.schemas.containers import ContainersComposeSpec
from ..models.shared_store import SharedStore
from ..modules.mounted_fs import MountedVolumes

_logger = logging.getLogger(__name__)


async def store_compose_spec(
    app: FastAPI,
    containers_compose_spec: ContainersComposeSpec,
):
    settings: ApplicationSettings = app.state.settings
    shared_store: SharedStore = app.state.shared_store
    mounted_volumes: MountedVolumes = app.state.mounted_volumes

    async with shared_store:
        compose_spec_validation: ComposeSpecValidation = (
            await get_and_validate_compose_spec(
                settings=settings,
                compose_file_content=containers_compose_spec.docker_compose_yaml,
                mounted_volumes=mounted_volumes,
            )
        )
        shared_store.compose_spec = compose_spec_validation.compose_spec
        shared_store.container_names = compose_spec_validation.current_container_names
        shared_store.original_to_container_names = (
            compose_spec_validation.original_to_current_container_names
        )

    _logger.info("Validated compose-spec:\n%s", f"{shared_store.compose_spec}")

    assert shared_store.compose_spec
