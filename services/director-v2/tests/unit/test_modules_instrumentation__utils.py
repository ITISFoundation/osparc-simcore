import pytest
from pydantic import ByteSize, parse_obj_as
from simcore_service_director_v2.modules.instrumentation._utils import (
    get_label_from_size,
)


@pytest.mark.parametrize(
    "size, expected_bucket_name",
    [
        (-1123218213879128973978123, "0"),
        (-1, "0"),
        (0, "0"),
        (1023, "1024"),
        (parse_obj_as(ByteSize, "9GiB"), "9663676416"),
        (parse_obj_as(ByteSize, "9GiB") - 1, "9663676416"),
        (parse_obj_as(ByteSize, "9GiB") + 1, "10737418240"),
        (parse_obj_as(ByteSize, "100GiB"), "107374182400"),
        (1238731278213782138723789132897321987, "107374182400"),
    ],
)
def test_get_label_from_size(size: ByteSize | int, expected_bucket_name: str):
    result_label: dict[str, str] = get_label_from_size(size)
    result = result_label["byte_size"]

    file_size = parse_obj_as(ByteSize, size).human_readable()
    result_size = parse_obj_as(ByteSize, result).human_readable()
    expected_bucket_size = parse_obj_as(ByteSize, expected_bucket_name).human_readable()

    assert (
        result == expected_bucket_name
    ), f"size={size}, file_size={file_size}, result_size={result_size}, expected_size={expected_bucket_size}"
