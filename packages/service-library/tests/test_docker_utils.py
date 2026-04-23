# pylint: disable=protected-access
from datetime import UTC, datetime

import pytest
from servicelib.docker_utils import DOCKER_HUB_HOST, get_image_complete_url, to_datetime
from settings_library.docker_registry import RegistrySettings

NOW = datetime.now(tz=UTC)


@pytest.fixture
def private_registry_settings() -> RegistrySettings:
    return RegistrySettings.model_validate(
        {
            "REGISTRY_AUTH": "True",
            "REGISTRY_USER": "user",
            "REGISTRY_PW": "password",
            "REGISTRY_SSL": "True",
            "REGISTRY_URL": "registry:5000",
        }
    )


@pytest.fixture
def empty_registry_settings() -> RegistrySettings:
    # NOTE: REGISTRY_URL has min_length=1, so use a value that cannot match any image
    return RegistrySettings.model_validate(
        {
            "REGISTRY_AUTH": "False",
            "REGISTRY_USER": "",
            "REGISTRY_PW": "",
            "REGISTRY_SSL": "False",
            "REGISTRY_URL": "unmatched-registry-host",
        }
    )


@pytest.mark.parametrize(
    "image, expected_url",
    [
        # private registry: image must hit the private-registry branch (https when REGISTRY_AUTH)
        pytest.param(
            "registry:5000/simcore/services/dynamic/tissue-properties:1.0.2",
            "https://registry:5000/simcore/services/dynamic/tissue-properties:1.0.2",
            id="private-registry-with-port",
        ),
    ],
)
def test_get_image_complete_url_private_registry(
    private_registry_settings: RegistrySettings,
    image: str,
    expected_url: str,
):
    assert f"{get_image_complete_url(image, private_registry_settings)}" == expected_url


@pytest.mark.parametrize(
    "image, expected_url",
    [
        pytest.param(
            "nginx:latest",
            f"https://{DOCKER_HUB_HOST}/library/nginx:latest",
            id="dockerhub-official-implicit",
        ),
        pytest.param(
            "nginx:1.25.4",
            f"https://{DOCKER_HUB_HOST}/library/nginx:1.25.4",
            id="dockerhub-official-tagged",
        ),
        pytest.param(
            "library/nginx:latest",
            f"https://{DOCKER_HUB_HOST}/library/nginx:latest",
            id="dockerhub-official-explicit-library",
        ),
        pytest.param(
            "itisfoundation/sleeper:1.0.0",
            f"https://{DOCKER_HUB_HOST}/itisfoundation/sleeper:1.0.0",
            id="dockerhub-namespaced",
        ),
        pytest.param(
            "quay.io/foo/bar:tag",
            "https://quay.io/foo/bar:tag",
            id="external-registry-with-dot",
        ),
        # NOTE: regression - image with explicit `:port` and no dot in host MUST NOT be treated
        # as a Dockerhub image. Previously this returned
        # https://registry-1.docker.io/registry:5000/... which 404s.
        pytest.param(
            "registry:5000/simcore/services/dynamic/tissue-properties:1.0.2",
            "https://registry:5000/simcore/services/dynamic/tissue-properties:1.0.2",
            id="regression-private-registry-host-port-no-dot",
        ),
        pytest.param(
            "myregistry:443/foo/bar:1.0",
            # NOTE: yarl strips the default https port (:443) from the URL
            "https://myregistry/foo/bar:1.0",
            id="regression-private-registry-https-default-port",
        ),
    ],
)
def test_get_image_complete_url_without_matching_private_registry(
    empty_registry_settings: RegistrySettings,
    image: str,
    expected_url: str,
):
    # When the image string does not contain the configured REGISTRY_URL, the function
    # falls back to the heuristic. Verify it correctly distinguishes Dockerhub images
    # from registries advertised as `host:port` (no dot in host).
    assert f"{get_image_complete_url(image, empty_registry_settings)}" == expected_url


@pytest.mark.parametrize(
    "docker_time, expected_datetime",
    [
        (
            "2023-03-21T00:00:00Z",
            datetime(2023, 3, 21, 0, 0, tzinfo=UTC),
        ),
        (
            "2023-12-31T23:59:59Z",
            datetime(2023, 12, 31, 23, 59, 59, tzinfo=UTC),
        ),
        (
            "2020-10-09T12:28:14.771034099Z",
            datetime(2020, 10, 9, 12, 28, 14, 771034, tzinfo=UTC),
        ),
        (
            "2020-10-09T12:28:14.123456099Z",
            datetime(2020, 10, 9, 12, 28, 14, 123456, tzinfo=UTC),
        ),
        (
            "2020-10-09T12:28:14.12345Z",
            datetime(2020, 10, 9, 12, 28, 14, 123450, tzinfo=UTC),
        ),
        (
            "2023-03-15 13:01:21.774501",
            datetime(2023, 3, 15, 13, 1, 21, 774501, tzinfo=UTC),
        ),
        (f"{NOW}", NOW),
        (NOW.strftime("%Y-%m-%dT%H:%M:%S.%f"), NOW),
    ],
)
def test_to_datetime(docker_time: str, expected_datetime: datetime):
    received_datetime = to_datetime(docker_time)
    assert received_datetime == expected_datetime
