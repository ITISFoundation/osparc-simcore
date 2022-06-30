# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import re

import pytest

# TODO: add test with REGEX_DY_SERVICE_PROXY, TODO: add test with  REGEX_DY_SERVICE_SIDECAR,
from simcore_service_director_v2.models.schemas.constants import (
    DYNAMIC_SIDECAR_DOCKER_IMAGE_RE,
)


@pytest.mark.parametrize(
    "sample",
    [
        "itisfoundation/dynamic-sidecar:staging-github-staging_diolkos1-2022-06-15--15-04.75ddf7e3fb86944ef95fcf77e4075464848121f1",
        "itisfoundation/dynamic-sidecar:hotfix-github-2022-06-24--12-34.162bfe899d6b62d808e70a07da280fd390bc4434",
        "itisfoundation/dynamic-sidecar:hotfix-v1-28-1-github-testbuild-latest",
        "itisfoundation/dynamic-sidecar:staging-github-latest",
        "itisfoundation/dynamic-sidecar:release-github-v1.28.0-2022-05-30--14-52.62c4c48b1846ecaa8280773f48a2f14bf0f3047b",
        "itisfoundation/dynamic-sidecar:master-github-2022-06-24--14-35.38add6817bc8cafabc14ec7dacd9b249daa3a11e",
    ],
)
def test_passes_DYNAMIC_SIDECAR_DOCKER_IMAGE_RE(sample: str):

    assert re.match(DYNAMIC_SIDECAR_DOCKER_IMAGE_RE, sample)
