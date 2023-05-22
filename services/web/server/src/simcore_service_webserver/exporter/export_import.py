import logging
from pathlib import Path

from aiohttp import web

from .archiving import zip_folder
from .formatters import BaseFormatter, FormatterV2

log = logging.getLogger(__name__)


async def study_export(
    app: web.Application,
    tmp_dir: str,
    project_id: str,
    user_id: int,
    product_name: str,
    archive: bool = False,
    formatter_class: type[BaseFormatter] = FormatterV2,
) -> Path:
    """
    Generates a folder with all the data necessary for exporting a project.
    If archive is True, an archive will always be produced.

    returns: directory if archive is True else a compressed archive is returned
    """

    # storage area for the project data
    base_temp_dir = Path(tmp_dir)
    destination = base_temp_dir / project_id
    destination.mkdir(parents=True, exist_ok=True)

    # The formatter will always be chosen to be the highest availabel version
    formatter = formatter_class(root_folder=destination)
    await formatter.format_export_directory(
        app=app, project_id=project_id, user_id=user_id, product_name=product_name
    )

    if archive is False:
        # returns the path to the temporary directory containing the study data
        return destination

    # an archive is always produced when compression is active
    archive_path = await zip_folder(
        folder_to_zip=base_temp_dir, destination_folder=base_temp_dir
    )

    return archive_path
