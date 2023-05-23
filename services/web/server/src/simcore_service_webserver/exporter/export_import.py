import logging
from pathlib import Path

from aiohttp import web

from .archiving import zip_folder
from .sds.formatter import create_sds_directory

log = logging.getLogger(__name__)


async def study_export(
    app: web.Application, tmp_dir: str, project_id: str, user_id: int, product_name: str
) -> Path:
    """
    Generates a folder with all the data necessary for exporting a project.
    return: path to compressed archive
    """

    base_temp_dir = Path(tmp_dir)
    destination = base_temp_dir / f"sds_{project_id}"
    destination.mkdir(parents=True, exist_ok=True)

    await create_sds_directory(
        app=app,
        root_folder=destination,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
    )

    archive_path = await zip_folder(
        folder_to_zip=destination,
        destination_folder=base_temp_dir,
        project_id=project_id,
    )

    return archive_path
