import sys
from pathlib import Path
from typing import List, Tuple
from uuid import UUID

from models_library.projects import ProjectID
from pytest_simcore.helpers.utils_login import AUserDict, log_client_in
from simcore_service_webserver.security_roles import UserRole
from yarl import URL

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

DATA_DIR = CURRENT_DIR.parent.parent / "data"
assert DATA_DIR.exists(), "expected folder under tests/data"

API_VERSION = "v0"
API_PREFIX = "/" + API_VERSION

# store only lowercase "v1", "v2", etc...
SUPPORTED_EXPORTER_VERSIONS = {"v1", "v2"}


async def _login_user(client) -> AUserDict:
    """returns a logged in regular user"""
    return await log_client_in(client=client, user_data={"role": UserRole.USER.name})


async def _import_study_from_file(client, file_path: Path) -> str:
    url_import = client.app.router["import_project"].url_for()
    assert url_import == URL(API_PREFIX + "/projects:import")

    data = {"fileName": open(file_path, mode="rb")}
    async with await client.post(url_import, data=data, timeout=10) as import_response:
        assert import_response.status == 200, await import_response.text()
        reply_data = await import_response.json()
        assert reply_data.get("data") is not None

    imported_project_uuid = reply_data["data"]["uuid"]
    return imported_project_uuid


def get_exported_projects() -> List[Path]:
    # These files are generated from the front-end
    # when the formatter be finished
    exporter_dir = DATA_DIR / "exporter"
    assert exporter_dir.exists()
    exported_files = [x for x in exporter_dir.glob("*.osparc")]
    assert exported_files, "expected *.osparc files, none found"
    return exported_files


async def login_user_and_import_study(
    client, export_version
) -> Tuple[ProjectID, AUserDict]:
    user = await _login_user(client)
    export_file_name = export_version.name
    version_from_name = export_file_name.split("#")[0]

    assert_error = (
        f"The '{version_from_name}' version' is not present in the supported versions: "
        f"{SUPPORTED_EXPORTER_VERSIONS}. If it's a new version please remember to add it."
    )
    assert version_from_name in SUPPORTED_EXPORTER_VERSIONS, assert_error

    imported_project_uuid = await _import_study_from_file(client, export_version)

    return UUID(imported_project_uuid), user
