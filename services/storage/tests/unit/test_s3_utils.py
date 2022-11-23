# pylint: disable=redefined-outer-name
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from pydantic import ByteSize, parse_obj_as
from pytest_simcore.helpers.utils_parametrizations import byte_size_ids
from simcore_service_storage.s3_utils import (
    _MULTIPART_MAX_NUMBER_OF_PARTS,
    _MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE,
    compute_num_file_chunks,
)


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
        (parse_obj_as(ByteSize, "9431773844"), 900, parse_obj_as(ByteSize, "10Mib")),
    ],
    ids=byte_size_ids,
)
def test_compute_num_file_chunks(
    file_size: ByteSize, expected_num_chunks: int, expected_chunk_size: ByteSize
):
    num_chunks, chunk_size = compute_num_file_chunks(file_size)
    assert num_chunks == expected_num_chunks
    assert chunk_size == expected_chunk_size


def test_enormous_file_size_raises_value_error():
    enormous_file_size = parse_obj_as(
        ByteSize,
        (
            max(_MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE)
            * _MULTIPART_MAX_NUMBER_OF_PARTS
            + 1
        ),
    )
    with pytest.raises(ValueError):
        compute_num_file_chunks(enormous_file_size)
