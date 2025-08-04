# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from models_library.projects import ProjectID
from pytest_simcore.helpers.webserver_projects import new_project


@pytest.fixture(scope="session")
def fake_workbench_payload(tests_data_dir: Path) -> dict:
    file_path = tests_data_dir / "workbench_sleeper_payload.json"
    with file_path.open() as fp:
        return json.load(fp)


@pytest.fixture
def fake_project(fake_data_dir: Path, fake_workbench_payload: dict) -> dict:
    project: dict = {}
    with (fake_data_dir / "fake-project.json").open() as fp:
        project = json.load(fp)
    project["workbench"] = fake_workbench_payload["workbench"]
    return project


@pytest.fixture
def project_id() -> ProjectID:
    return uuid4()


@pytest.fixture
async def user_project(
    client,
    fake_project: dict,
    logged_user: dict,
    project_id: ProjectID,
    tests_data_dir: Path,
    osparc_product_name: str,
) -> AsyncIterator[dict]:
    fake_project["prjOwner"] = logged_user["name"]
    fake_project["uuid"] = f"{project_id}"

    async with new_project(
        fake_project,
        client.app,
        user_id=logged_user["id"],
        product_name=osparc_product_name,
        tests_data_dir=tests_data_dir,
    ) as project:
        yield project
