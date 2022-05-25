import asyncio
import logging
from asyncio import Lock
from models_library.docker import DockerImage

from servicelib.logging_utils import log_decorator

from .catalog_client import get_shared_client, get_images_to_pull
from .models import AppState
from .settings import ImagePullerSettings
from .docker_api import pull_image

logger = logging.getLogger(__name__)


@log_decorator(logger=logger)
async def worker(app_state: AppState) -> None:
    if app_state.worker_lock.locked():
        logger.info("Skipping. A task is already pulling images")
        return

    async with app_state.worker_lock:
        images_to_pull: list[DockerImage] = await get_images_to_pull(
            app_state.catalog_client
        )
        for image in images_to_pull:
            await pull_image(image)

        # TODO: add here a task to remove older images


async def async_main(settings: ImagePullerSettings) -> None:
    app_state = AppState(
        settings=settings,
        worker_lock=Lock(),
        catalog_client=get_shared_client(settings),
    )

    while True:
        asyncio.create_task(worker(app_state=app_state))
        await asyncio.sleep(settings.IMAGE_PULLER_CHECK_INTERVAL_S)


def main() -> None:
    settings: ImagePullerSettings = ImagePullerSettings.create_from_envs()
    logging.basicConfig(level=settings.IMAGE_PULLER_LOG_LEVEL.value)
    logging.root.setLevel(settings.IMAGE_PULLER_LOG_LEVEL.value)
    logger.info("Application settings %s", settings.json(indent=2))

    asyncio.get_event_loop().run_until_complete(async_main(settings))


if __name__ == "__main__":
    main()
