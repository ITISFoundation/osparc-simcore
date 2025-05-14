# pylint: disable=protected-access
from datetime import datetime, timezone

import pytest
from servicelib.docker_utils import get_image_name_and_tag, to_datetime
from yarl import URL

NOW = datetime.now(tz=timezone.utc)


@pytest.mark.parametrize(
    "docker_time, expected_datetime",
    [
        (
            "2023-03-21T00:00:00Z",
            datetime(2023, 3, 21, 0, 0, tzinfo=timezone.utc),
        ),
        (
            "2023-12-31T23:59:59Z",
            datetime(2023, 12, 31, 23, 59, 59, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.771034099Z",
            datetime(2020, 10, 9, 12, 28, 14, 771034, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.123456099Z",
            datetime(2020, 10, 9, 12, 28, 14, 123456, tzinfo=timezone.utc),
        ),
        (
            "2020-10-09T12:28:14.12345Z",
            datetime(2020, 10, 9, 12, 28, 14, 123450, tzinfo=timezone.utc),
        ),
        (
            "2023-03-15 13:01:21.774501",
            datetime(2023, 3, 15, 13, 1, 21, 774501, tzinfo=timezone.utc),
        ),
        (f"{NOW}", NOW),
        (NOW.strftime("%Y-%m-%dT%H:%M:%S.%f"), NOW),
    ],
)
def test_to_datetime(docker_time: str, expected_datetime: datetime):
    received_datetime = to_datetime(docker_time)
    assert received_datetime == expected_datetime


@pytest.mark.parametrize(
    "image, expected_name, expected_tag",
    [
        ("my_image:latest", "my_image", "latest"),
        ("my_image:1.1.1", "my_image", "1.1.1"),
        ("my_image:latest@sha256:1234567890abcdef", "my_image", "latest"),
        ("my_image:1.1.1@sha256:1234567890abcdef", "my_image", "1.1.1"),
        ("docker.io/my_image:latest", "docker.io/my_image", "latest"),
        ("docker.io/my_image:1.1.1", "docker.io/my_image", "1.1.1"),
        (
            "docker.io/my_image:1.1.1@sha256:1234567890abcdef",
            "docker.io/my_image",
            "1.1.1",
        ),
        ("registry:5000/my_image:1.1.1", "registry:5000/my_image", "1.1.1"),
        (
            "registry:5000/my_image:1.1.1@sha256:1234567890abcdef",
            "registry:5000/my_image",
            "1.1.1",
        ),
        (
            "registry:5000/simcore/services/dynamic/jupyter-fenics:1.1.2",
            "registry:5000/simcore/services/dynamic/jupyter-fenics",
            "1.1.2",
        ),
    ],
)
def test_get_image_name_and_tag(image: str, expected_name: str, expected_tag: str):
    name, tag = get_image_name_and_tag(URL(image))
    assert name == expected_name
    assert tag == expected_tag
