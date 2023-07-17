# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import itertools
from pathlib import Path

import pytest
from simcore_service_webserver._resources import webserver_resources


@pytest.fixture
def app_resources(package_dir: Path) -> list[str]:
    resource_names = []
    base = package_dir
    for name in ("api", "templates"):
        folder = base / name
        resource_names += [
            f"{p.relative_to(base)}"
            for p in itertools.chain(folder.rglob("*.y*ml"), folder.rglob("*.jinja2"))
        ]

    assert resource_names
    return resource_names


def test_webserver_resources(app_resources: list[str]):
    for resource_name in app_resources:
        assert webserver_resources.get_path(resource_name).exists()


def test_paths_might_not_exist():
    some_path = webserver_resources.get_path("fake_resource_name")
    assert some_path
    assert not some_path.exists()
