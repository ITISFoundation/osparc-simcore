# pylint: disable=unused-argument
# pylint: disable=redefined-outer-name
# pylint: disable=unused-variable
import logging
import sys
from pathlib import Path
from os.path import relpath
import pytest
from collections import namedtuple

log = logging.getLogger(__name__)

# Conventions
SHARED = 'shared'
OPENAPI_MAIN_FILENAME = 'openapi.yaml'


@pytest.fixture(scope='session')
def here():
    return Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

@pytest.fixture(scope='session')
def api_specs_dir(here):
    specs_dir = here.parent / "specs"
    return specs_dir

@pytest.fixture(scope='session')
def api_specs_info(api_specs_dir):
    """
        Returns a namedtuple with info on every
    """
    service_dirs = [d for d in api_specs_dir.iterdir() if d.is_dir() and not d.name.endswith(SHARED)]

    info_cls = namedtuple("ApiSpecsInfo", "service version openapi_path url_path".split())
    info = []
    for srv_dir in service_dirs:
        version_dirs = [d for d in srv_dir.iterdir() if d.is_dir() and not d.name.endswith(SHARED)]
        for ver_dir in version_dirs:
            openapi_path = ver_dir / OPENAPI_MAIN_FILENAME
            if openapi_path.exists():
                info.append( info_cls(
                    service=srv_dir.name,
                    version=ver_dir.name,
                    openapi_path=openapi_path,
                    url_path=relpath(openapi_path, srv_dir) # ${version}/openapi.yaml
                ))
    # https://yarl.readthedocs.io/en/stable/api.html#yarl.URL
    # [scheme:]//[user[:password]@]host[:port][/path][?query][#fragment]
    return info
