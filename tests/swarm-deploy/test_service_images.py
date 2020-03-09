# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import subprocess
from typing import Dict
import pytest


# search ujson in all _base.txt and add here all services that contains it
@pytest.mark.parametrize("service", [
    'director',
    'webserver',
    'storage',
    'catalog'
])
def test_ujson_installation(service:str, osparc_deploy: Dict):
    # tets failing installation undetected
    # and fixed in PR https://github.com/ITISFoundation/osparc-simcore/pull/1353
    image_name = osparc_deploy['simcore']['services'][service]['image']

    assert subprocess.run(
        f'docker run -t --rm {image_name} python -c "import ujson; print(ujson.__version__)"',
        shell=True,
        check=True,
    )
