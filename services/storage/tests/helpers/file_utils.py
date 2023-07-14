import json
from pathlib import Path
from time import perf_counter
from typing import Final

import aiofiles
import pytest
from aiohttp import ClientSession, web
from models_library.api_schemas_storage import FileUploadSchema
from pydantic import AnyUrl, ByteSize, parse_obj_as
from servicelib.utils import logged_gather
from simcore_service_storage.s3_client import ETag, MultiPartUploadLinks, UploadedPart

_SENDER_CHUNK_SIZE: Final[int] = parse_obj_as(ByteSize, "16Mib")


async def _file_sender(
    file: Path, *, offset: int, bytes_to_send: int, raise_while_uploading: bool
):
    chunk_size = _SENDER_CHUNK_SIZE
    if raise_while_uploading:
        # to ensure we can raise before it is done
        chunk_size = min(_SENDER_CHUNK_SIZE, int(file.stat().st_size / 3))
    async with aiofiles.open(file, "rb") as f:
        await f.seek(offset)
        num_read_bytes = 0
        while chunk := await f.read(min(chunk_size, bytes_to_send - num_read_bytes)):
            num_read_bytes += len(chunk)
            yield chunk
            if raise_while_uploading:
                raise RuntimeError("we were asked to raise here!")


async def upload_file_part(
    session: ClientSession,
    file: Path,
    part_index: int,
    file_offset: int,
    this_file_chunk_size: int,
    num_parts: int,
    upload_url: AnyUrl,
    raise_while_uploading: bool = False,
) -> tuple[int, ETag]:
    print(
        f"--> uploading {this_file_chunk_size=} of {file=}, [{part_index+1}/{num_parts}]..."
    )
    response = await session.put(
        upload_url,
        data=_file_sender(
            file,
            offset=file_offset,
            bytes_to_send=this_file_chunk_size,
            raise_while_uploading=raise_while_uploading,
        ),
        headers={
            "Content-Length": f"{this_file_chunk_size}",
        },
    )
    response.raise_for_status()
    # NOTE: the response from minio does not contain a json body
    assert response.status == web.HTTPOk.status_code
    assert response.headers
    assert "Etag" in response.headers
    received_e_tag = json.loads(response.headers["Etag"])
    print(
        f"--> completed upload {this_file_chunk_size=} of {file=}, [{part_index+1}/{num_parts}], {received_e_tag=}"
    )
    return (part_index, received_e_tag)


async def upload_file_to_presigned_link(
    file: Path, file_upload_link: FileUploadSchema | MultiPartUploadLinks
) -> list[UploadedPart]:
    file_size = file.stat().st_size

    start = perf_counter()
    print(f"--> uploading {file=}")
    async with ClientSession() as session:
        file_chunk_size = int(file_upload_link.chunk_size)
        num_urls = len(file_upload_link.urls)
        last_chunk_size = file_size - file_chunk_size * (num_urls - 1)
        upload_tasks = []
        for index, upload_url in enumerate(file_upload_link.urls):
            this_file_chunk_size = (
                file_chunk_size if (index + 1) < num_urls else last_chunk_size
            )
            upload_tasks.append(
                upload_file_part(
                    session,
                    file,
                    index,
                    index * file_chunk_size,
                    this_file_chunk_size,
                    num_urls,
                    upload_url,
                )
            )
        results = await logged_gather(*upload_tasks, max_concurrency=2)
    part_to_etag = [
        UploadedPart(number=index + 1, e_tag=e_tag) for index, e_tag in results
    ]
    print(
        f"--> upload of {file=} of {file_size=} completed in {perf_counter() - start}"
    )
    return part_to_etag


def parametrized_file_size(size_str: str):
    return pytest.param(parse_obj_as(ByteSize, size_str), id=size_str)
