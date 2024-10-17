from typing import Final

from pydantic import ByteSize, TypeAdapter

_MULTIPART_MAX_NUMBER_OF_PARTS: Final[int] = 10000

# this is artifically defined, if possible we keep a maximum number of requests for parallel
# uploading. If that is not possible then we create as many upload part as the max part size allows
_MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE: Final[list[ByteSize]] = [
    TypeAdapter(ByteSize).validate_python(x)
    for x in [
        "10Mib",
        "50Mib",
        "100Mib",
        "200Mib",
        "400Mib",
        "600Mib",
        "800Mib",
        "1Gib",
        "2Gib",
        "3Gib",
        "4Gib",
        "5Gib",
    ]
]


def compute_num_file_chunks(file_size: ByteSize) -> tuple[int, ByteSize]:
    for chunk in _MULTIPART_UPLOADS_TARGET_MAX_PART_SIZE:
        num_upload_links = int(file_size / chunk) + (1 if file_size % chunk > 0 else 0)
        if num_upload_links < _MULTIPART_MAX_NUMBER_OF_PARTS:
            return (num_upload_links, chunk)
    msg = f"Could not determine number of upload links for {file_size=}"
    raise ValueError(
        msg,
    )
