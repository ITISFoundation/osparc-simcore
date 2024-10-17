# pylint: disable=redefined-outer-name
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from aws_library.s3._utils import (
    _MULTIPART_MAX_NUMBER_OF_PARTS,
    _MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE,
    compute_num_file_chunks,
)
from pydantic import ByteSize, TypeAdapter
from pytest_simcore.helpers.parametrizations import byte_size_ids


@pytest.mark.parametrize(
    "file_size, expected_num_chunks, expected_chunk_size",
    [
        (
            TypeAdapter(ByteSize).validate_python("5Mib"),
            1,
            TypeAdapter(ByteSize).validate_python("10Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("10Mib"),
            1,
            TypeAdapter(ByteSize).validate_python("10Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("20Mib"),
            2,
            TypeAdapter(ByteSize).validate_python("10Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("50Mib"),
            5,
            TypeAdapter(ByteSize).validate_python("10Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("150Mib"),
            15,
            TypeAdapter(ByteSize).validate_python("10Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("550Mib"),
            55,
            TypeAdapter(ByteSize).validate_python("10Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("560Gib"),
            5735,
            TypeAdapter(ByteSize).validate_python("100Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("5Tib"),
            8739,
            TypeAdapter(ByteSize).validate_python("600Mib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("15Tib"),
            7680,
            TypeAdapter(ByteSize).validate_python("2Gib"),
        ),
        (
            TypeAdapter(ByteSize).validate_python("9431773844"),
            900,
            TypeAdapter(ByteSize).validate_python("10Mib"),
        ),
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
    enormous_file_size = TypeAdapter(ByteSize).validate_python(
        (
            max(_MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE)
            * _MULTIPART_MAX_NUMBER_OF_PARTS
            + 1
        ),
    )
    with pytest.raises(ValueError):
        compute_num_file_chunks(enormous_file_size)
