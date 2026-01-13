# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from typing import Any
from uuid import UUID

import pytest
from faker import Faker
from fastapi import FastAPI
from pytest_mock import MockType
from pytest_simcore.helpers.webserver_fake_ports_data import (
    PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA,
)
from simcore_service_api_server.models.schemas.studies import StudyID


@pytest.fixture
def study_id(faker: Faker) -> StudyID:
    return faker.uuid4()


@pytest.fixture
def fake_study_ports() -> list[dict[str, Any]]:
    # NOTE: Reuses fakes used to test web-server API responses of /projects/{project_id}/metadata/ports
    # as responses in this mock. SEE services/web/server/tests/unit/with_dbs/02/test_projects_ports_handlers.py
    return deepcopy(PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA)


@pytest.fixture
def fake_study_id(faker: Faker) -> UUID:
    return faker.uuid4()


@pytest.fixture
def mock_dependency_get_celery_task_manager(app: FastAPI, mock_task_manager_object: MockType) -> MockType:
    from simcore_service_api_server.api.dependencies.celery import get_task_manager  # noqa: PLC0415

    app.dependency_overrides[get_task_manager] = lambda: mock_task_manager_object
    yield mock_task_manager_object
    app.dependency_overrides.pop(get_task_manager, None)
