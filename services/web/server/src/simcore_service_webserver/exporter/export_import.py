import json

from pathlib import Path

from aiohttp import web

from .archiving import zip_folder
from simcore_service_webserver.projects.projects_api import get_project_for_user

# used in the future, will change if export format changes
EXPORT_VERSION = "1"


async def generate_directory_contents(
    app: web.Application, dir_path: Path, project_id: str, user_id: int
) -> None:
    text_file = dir_path / "manifest.json"
    project_json = dir_path / "project.json"

    project_data = await get_project_for_user(
        app=app,
        project_uuid=project_id,
        user_id=user_id,
        include_templates=True,
        include_state=True,
    )

    # TODO: maybe move this to a Pydantic model
    manifest = {
        "version": EXPORT_VERSION,
    }

    text_file.write_text(json.dumps(manifest))
    project_json.write_text(json.dumps(project_data))


# neagu-wkst:9081/v0/projects/d3cfd554-3ed9-11eb-9dd5-02420a0000f6/export?compressed=true
async def study_export(
    app: web.Application,
    tmp_dir: str,
    project_id: str,
    user_id: int,
    archive: bool = False,
    compress: bool = False,
) -> Path:
    """
    Generates a folder with all the data necessary for exporting a project.
    If compress is True, an archive will always be produced.

    returns:
        directory: if both archive and compress are False
        uncompressed archive: if archive is True and compress is False
        compressed archive: if both archive and compress are True
    """
    # acquire some random template
    # so the project model must use a from dict to dict serialization
    # also this should support options for zipping

    # storage area for the project data
    destination = Path(tmp_dir) / project_id
    destination.mkdir(parents=True, exist_ok=True)

    await generate_directory_contents(
        app=app, dir_path=destination, project_id=project_id, user_id=user_id
    )

    # at this point there is no more temp directory
    if archive is False and compress is False:
        # returns the path to the temporary directory containing the project
        return destination

    if archive and compress is False:
        archive_path = await zip_folder(
            project_id=project_id, input_path=destination, no_compression=True
        )
        return archive_path

    # an archive is always produced when compression is active
    # compress is always True in this situationå
    archive_path = await zip_folder(
        project_id=project_id, input_path=destination, no_compression=False
    )

    return archive_path


async def study_import(path: Path) -> None:
    """ Creates a project from a given exported project """
