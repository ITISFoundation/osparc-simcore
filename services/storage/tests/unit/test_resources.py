# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import logging
from pathlib import Path

import pytest
from simcore_service_storage.resources import storage_resources

log = logging.getLogger(__name__)


@pytest.fixture
def app_resources(package_dir: Path) -> list[str]:
    return [
        str(p.relative_to(package_dir)) for p in (package_dir / "api").rglob("*.y*ml")
    ]


def test_paths(app_resources: list[str]):
    for resource_name in app_resources:
        assert storage_resources.get_path(resource_name).exists()

    some_path = storage_resources.get_path("fake_resource_name")
    assert some_path
    assert not some_path.exists()
