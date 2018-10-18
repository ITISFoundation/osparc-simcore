# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-import

import io
import logging
import pathlib

import pytest

# under test
from simcore_service_storage.resources import resources
from simcore_service_storage.settings import RSC_CONFIG_DIR_KEY, RSC_OPENAPI_DIR_KEY

log = logging.getLogger(__name__)

@pytest.fixture
def app_resources(package_dir):
    resource_names = []
    for name in (RSC_CONFIG_DIR_KEY, RSC_OPENAPI_DIR_KEY):
        folder = package_dir / name
        resource_names += [ str(p.relative_to(package_dir)) for p in folder.rglob("*.y*ml") ]

    return resource_names

#------------------------------------------------------------------------------

def test_resource_io_utils(app_resources):

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
    exposed = [getattr(resources, name) for name in dir(resources) if name.startswith("RESOURCES")]

    for resource_name in exposed:
        assert resources.exists(resource_name)
        assert resources.isdir(resource_name)
        assert resources.listdir(resource_name)

def test_paths(app_resources):
    for resource_name in app_resources:
        assert resources.get_path(resource_name).exists()

    # WARNING!
    some_path = resources.get_path("fake_resource_name")
    assert some_path and not some_path.exists()
