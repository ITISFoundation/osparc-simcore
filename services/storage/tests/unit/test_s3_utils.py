# pylint: disable=redefined-outer-name
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from pydantic import ByteSize, parse_obj_as
from simcore_service_storage.s3_utils import compute_num_file_chunks


@pytest.mark.xfail(reason="will work soon")
@pytest.mark.parametrize(
    "file_size, expected_num_chunks, expected_chunk_size",
    [
        (parse_obj_as(ByteSize, "5Mib"), 1, parse_obj_as(ByteSize, "10Mib")),
        (parse_obj_as(ByteSize, "10Mib"), 1, parse_obj_as(ByteSize, "10Mib")),
        (parse_obj_as(ByteSize, "20Mib"), 2, parse_obj_as(ByteSize, "10Mib")),
        (parse_obj_as(ByteSize, "50Mib"), 5, parse_obj_as(ByteSize, "10Mib")),
        (parse_obj_as(ByteSize, "150Mib"), 15, parse_obj_as(ByteSize, "10Mib")),
        (parse_obj_as(ByteSize, "550Mib"), 55, parse_obj_as(ByteSize, "10Mib")),
        (parse_obj_as(ByteSize, "560Gib"), 5735, parse_obj_as(ByteSize, "100Mib")),
        (parse_obj_as(ByteSize, "5Tib"), 8739, parse_obj_as(ByteSize, "600Mib")),
        (parse_obj_as(ByteSize, "15Tib"), 7680, parse_obj_as(ByteSize, "2Gib")),
    ],
)
def test_compute_num_file_chunks(
    file_size: ByteSize, expected_num_chunks: int, expected_chunk_size: ByteSize
):
    num_chunks, chunk_size = compute_num_file_chunks(file_size)
    assert num_chunks == expected_num_chunks
    assert chunk_size == expected_chunk_size
