import logging

from ...core.settings import ApplicationSettings
from ._docker import delete_volume, docker_client, get_dyv_volumes, is_volume_used
from ._s3 import store_to_s3

logger = logging.getLogger(__name__)


async def backup_and_remove_volumes(settings: ApplicationSettings) -> None:
    async with docker_client() as client:
        dyv_volumes: list[dict] = await get_dyv_volumes(client)

        if len(dyv_volumes) == 0:
            return

        cleaned_up_volumes_count = 0
        logger.info("Beginning cleanup.")
        for dyv_volume in dyv_volumes:
            volume_name = dyv_volume["Name"]

            if await is_volume_used(client, volume_name):
                logger.debug("Skipped in use docker volume: '%s'", volume_name)
                continue

            try:
                await store_to_s3(
                    volume_name=volume_name,
                    dyv_volume=dyv_volume,
                    s3_endpoint=settings.AGENT_VOLUMES_CLEANUP_S3_ENDPOINT,
                    s3_access_key=settings.AGENT_VOLUMES_CLEANUP_S3_ACCESS_KEY,
                    s3_secret_key=settings.AGENT_VOLUMES_CLEANUP_S3_SECRET_KEY,
                    s3_bucket=settings.AGENT_VOLUMES_CLEANUP_S3_BUCKET,
                    s3_region=settings.AGENT_VOLUMES_CLEANUP_S3_REGION,
                    s3_provider=settings.AGENT_VOLUMES_CLEANUP_S3_PROVIDER,
                    s3_retries=settings.AGENT_VOLUMES_CLEANUP_RETRIES,
                    s3_parallelism=settings.AGENT_VOLUMES_CLEANUP_PARALLELISM,
                    exclude_files=settings.AGENT_VOLUMES_CLEANUP_EXCLUDE_FILES,
                )
            except RuntimeError as e:
                logger.error("%s", e)
                continue

            logger.info(
                (
                    "Succesfully pushed data to S3 for zombie dynamic sidecar "
                    "docker volume: '%s'"
                ),
                volume_name,
            )

            await delete_volume(client, volume_name)
            logger.info("Removed docker volume: '%s'", volume_name)
            cleaned_up_volumes_count += 1

        if cleaned_up_volumes_count > 0:
            logger.info(
                (
                    "The dy-sidecar volume cleanup detected %s "
                    "zombie volumes on the current machine."
                ),
                cleaned_up_volumes_count,
            )
        else:
            logger.info("Found no zombie dy-sidecar volumes to cleanup.")
