# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

import io
import logging
from pathlib import Path
from typing import List

import pytest

# under test
from simcore_service_webserver.resources import resources

log = logging.getLogger(__name__)


@pytest.fixture
def app_resources(package_dir: Path) -> List[str]:
    resource_names = []
    base = package_dir
    for name in (resources.config_folder, "api"):
        folder = base / name
        resource_names += [str(p.relative_to(base)) for p in folder.rglob("*.y*ml")]

    return resource_names


# ------------------------------------------------------------------------------


def test_resource_io_utils(app_resources: List[str]):

    assert not resources.exists("fake_resource_name")

    for resource_name in app_resources:
        # existence
        assert resources.exists(resource_name)

        # context management
        ostream = None
        with resources.stream(resource_name) as ostream:
            assert isinstance(ostream, io.IOBase)
            assert ostream.read()

        assert ostream.closed


def test_named_resources():
    exposed = [
        getattr(resources, name)
        for name in dir(resources)
        if name.startswith("RESOURCES")
    ]

    for resource_name in exposed:
        assert resources.exists(resource_name)
        assert resources.isdir(resource_name)
        assert resources.listdir(resource_name)


def test_paths(app_resources: List[str]):
    for resource_name in app_resources:
        assert resources.get_path(resource_name).exists()

    # WARNING!
    some_path = resources.get_path("fake_resource_name")
    assert some_path and not some_path.exists()
