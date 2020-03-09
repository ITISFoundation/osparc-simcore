# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import subprocess
from typing import Dict
import pytest


@pytest.mark.parametrize("service", [
    'director',
    'webserver',
])
def test_ujson_installation(service:str, osparc_deploy: Dict):
    image_name = osparc_deploy['simcore']['services'][service]['image']

    assert subprocess.run(
        f'docker run -t --rm {image_name} python -c "import ujson; print(ujson.__version__)"',
        shell=True,
        check=True,
    )
