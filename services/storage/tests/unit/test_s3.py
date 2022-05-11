# pylint: disable=protected-access

import pytest
from simcore_service_storage import s3


@pytest.mark.parametrize(
    "url, expected",
    [
        ("https://ceph.com", "ceph.com"),
        ("http://ciao.com", "ciao.com"),
        ("http://local.address:8012", "local.address:8012"),
        ("https://remote.stragen.com:4432", "remote.stragen.com:4432"),
    ],
)
def test_minio_client_endpint(url: str, expected: str) -> None:
    assert s3._minio_client_endpint(url) == expected
