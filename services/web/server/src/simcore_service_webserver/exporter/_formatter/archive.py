from pathlib import Path

from aiohttp import web
from servicelib.archiving_utils import archive_dir

from ..exceptions import SDSException
from ._sds import create_sds_directory


async def _compress_dir(
    folder_to_zip: Path, destination_folder: Path, project_id: str
) -> Path:
    """compresses a folder and returns the path to the new archive"""

    archive_name: Path = destination_folder / f"sds_{project_id}.zip"
    if archive_name.is_file():
        msg = (
            f"Cannot archive '{folder_to_zip}' because "
            f"'{archive_name}' already exists"
        )
        raise SDSException(msg)

    await archive_dir(
        dir_to_compress=folder_to_zip,
        destination=archive_name,
        compress=True,
        store_relative_path=True,
    )

    return archive_name


async def get_sds_archive_path(
    app: web.Application, tmp_dir: str, project_id: str, user_id: int, product_name: str
) -> Path:
    """
    returns: the Path to an archive containing the SDS data from the study
    """

    base_temp_dir = Path(tmp_dir)
    destination = base_temp_dir / f"sds_{project_id}"
    destination.mkdir(parents=True, exist_ok=True)

    await create_sds_directory(
        app=app,
        base_path=destination,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
    )

    return await _compress_dir(
        folder_to_zip=destination,
        destination_folder=base_temp_dir,
        project_id=project_id,
    )
