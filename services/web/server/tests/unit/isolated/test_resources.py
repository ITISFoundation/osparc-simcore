# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from pathlib import Path

import pytest
from simcore_service_webserver._resources import webserver_resources


@pytest.fixture
def app_resources(package_dir: Path) -> list[str]:
    resource_names = []
    base = package_dir
    for name in (webserver_resources.config_folder, "api"):
        folder = base / name
        resource_names += [str(p.relative_to(base)) for p in folder.rglob("*.y*ml")]

    assert resource_names
    return resource_names


def test_named_resources():
    exposed = [
        getattr(webserver_resources, name)
        for name in dir(webserver_resources)
        if name.startswith("RESOURCES")
    ]

    for resource_name in exposed:
        assert webserver_resources.exists(resource_name)
        assert webserver_resources.isdir(resource_name)
        assert webserver_resources.listdir(resource_name)


def test_paths(app_resources: list[str]):
    for resource_name in app_resources:
        assert webserver_resources.get_path(resource_name).exists()

    some_path = webserver_resources.get_path("fake_resource_name")
    assert some_path
    assert not some_path.exists()
