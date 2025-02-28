import logging

from fastapi import FastAPI
from models_library.api_schemas_dynamic_sidecar.containers import DcokerComposeYamlStr

from ..core.settings import ApplicationSettings
from ..core.validation import ComposeSpecValidation, validate_compose_spec
from ..models.shared_store import SharedStore, get_shared_store
from ..modules.mounted_fs import MountedVolumes

_logger = logging.getLogger(__name__)


async def store_conpose_spec(
    app: FastAPI,
    *,
    docker_compose_yaml: DcokerComposeYamlStr,
) -> None:
    """
    Validates and stores the docker compose spec for the user services.
    """

    settings: ApplicationSettings = app.state.settings
    mounted_volumes: MountedVolumes = app.state.mounted_volumes
    shared_store: SharedStore = get_shared_store(app)

    async with shared_store:
        compose_spec_validation: ComposeSpecValidation = await validate_compose_spec(
            settings=settings,
            compose_file_content=docker_compose_yaml,
            mounted_volumes=mounted_volumes,
        )
        shared_store.compose_spec = compose_spec_validation.compose_spec
        shared_store.container_names = compose_spec_validation.current_container_names
        shared_store.original_to_container_names = (
            compose_spec_validation.original_to_current_container_names
        )

    _logger.info("Validated compose-spec:\n%s", f"{shared_store.compose_spec}")

    assert shared_store.compose_spec  # nosec
