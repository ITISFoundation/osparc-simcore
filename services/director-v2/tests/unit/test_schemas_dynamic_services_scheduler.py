# pylint: disable=redefined-outer-name

from pathlib import Path
import pytest
import json
from simcore_service_director_v2.models.schemas.dynamic_services.scheduler import (
    SchedulerData,
)


@pytest.fixture(
    scope="session",
    params=[
        "fake_scheduler_data.json",
        "fake_scheduler_data_compose_spec.json",
    ],
)
def fake_data_file_name(request):
    return request.param


@pytest.fixture
def fake_scheduler_data(mocks_dir: Path, fake_data_file_name: str) -> str:
    file = mocks_dir / fake_data_file_name
    assert file.exists()
    return file.read_text()


async def test_parse_saved_fake_scheduler_data(fake_scheduler_data: str) -> None:
    scheduler_data = SchedulerData.parse_obj(json.loads(fake_scheduler_data))
    assert scheduler_data
