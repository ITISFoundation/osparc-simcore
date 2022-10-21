import logging

import typer

from ..settings import ApplicationSettings
from ._docker import delete_volume, docker_client, get_dyv_volumes, is_volume_used
from ._s3 import store_to_s3

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


async def backup_and_remove_volumes(settings: ApplicationSettings) -> None:
    async with docker_client() as client:
        dyv_volumes: list[dict] = await get_dyv_volumes(client)

        if len(dyv_volumes) == 0:
            return

        cleaned_up_volumes_count = 0
        typer.echo("Beginning cleanup.")
        for dyv_volume in dyv_volumes:
            volume_name = dyv_volume["Name"]

            if await is_volume_used(client, volume_name):
                typer.echo(f"Skipped in use docker volume: '{volume_name}'")
                continue

            await store_to_s3(
                dyv_volume=dyv_volume,
                s3_endpoint=settings.S3_ENDPOINT,
                s3_access_key=settings.S3_ACCESS_KEY,
                s3_secret_key=settings.S3_SECRET_KEY,
                s3_bucket=settings.S3_BUCKET,
                s3_region=settings.S3_REGION,
                s3_provider=settings.S3_PROVIDER,
                s3_retries=settings.S3_RETRIES,
                s3_parallelism=settings.S3_PARALLELISM,
                exclude_files=settings.EXCLUDE_FILES,
            )
            typer.echo(
                "Succesfully pushed data to S3 for zombie dynamic sidecar "
                f"docker volume: '{volume_name}'"
            )

            await delete_volume(client, volume_name)
            typer.echo(f"Removed docker volume: '{volume_name}'")
            cleaned_up_volumes_count += 1

        if cleaned_up_volumes_count > 0:
            typer.echo(
                f"The dy-sidecar volume cleanup detected {cleaned_up_volumes_count} "
                "zombie volumes on the current machine."
            )
        else:
            typer.echo("Found no zombie dy-sidecar volumes to cleanup.")
