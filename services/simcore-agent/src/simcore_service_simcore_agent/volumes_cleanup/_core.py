import logging


from ..settings import ApplicationSettings
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
                logger.info("Skipped in use docker volume: '%s'", volume_name)
                continue

            await store_to_s3(
                dyv_volume=dyv_volume,
                s3_endpoint=settings.SIMCORE_AGENT_S3_ENDPOINT,
                s3_access_key=settings.SIMCORE_AGENT_S3_ACCESS_KEY,
                s3_secret_key=settings.SIMCORE_AGENT_S3_SECRET_KEY,
                s3_bucket=settings.SIMCORE_AGENT_S3_BUCKET,
                s3_region=settings.SIMCORE_AGENT_S3_REGION,
                s3_provider=settings.SIMCORE_AGENT_S3_PROVIDER,
                s3_retries=settings.SIMCORE_AGENT_S3_RETRIES,
                s3_parallelism=settings.SIMCORE_AGENT_S3_PARALLELISM,
                exclude_files=settings.SIMCORE_AGENT_EXCLUDE_FILES,
            )
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
