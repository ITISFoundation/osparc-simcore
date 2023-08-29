# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from copy import deepcopy
from typing import Any

import pytest
from faker import Faker
from pytest_simcore.helpers.faker_webserver import (
    PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA,
)
from simcore_service_api_server.models.schemas.studies import StudyID


@pytest.fixture
def study_id(faker: Faker) -> StudyID:
    return faker.uuid4()


@pytest.fixture
def fake_study_ports() -> list[dict[str, Any]]:
    # NOTE: Reuses fakes used to test web-server API responses of /projects/{project_id}/metadata/ports
    # as reponses in this mock. SEE services/web/server/tests/unit/with_dbs/02/test_projects_ports_handlers.py
    return deepcopy(PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA)
