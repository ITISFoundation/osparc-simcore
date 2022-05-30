import asyncio
import json
from pathlib import Path
from time import perf_counter
from typing import Final, Union

import aiofiles
from aiohttp import ClientSession, web
from models_library.api_schemas_storage import FileUploadSchema
from pydantic import AnyUrl, ByteSize, parse_obj_as
from simcore_service_storage.s3_client import ETag, MultiPartUploadLinks, UploadedPart

_SUB_CHUNKS: Final[int] = parse_obj_as(ByteSize, "16Mib")


async def _file_sender(file_name: Path, *, offset: int, bytes_to_send: int):
    async with aiofiles.open(file_name, "rb") as f:
        await f.seek(offset)
        num_read_bytes = 0
        while chunk := await f.read(min(_SUB_CHUNKS, bytes_to_send - num_read_bytes)):
            num_read_bytes += len(chunk)
            yield chunk


async def _upload_file_part(
    session: ClientSession,
    file: Path,
    part_index: int,
    file_offset: int,
    this_file_chunk_size: int,
    num_parts: int,
    upload_url: AnyUrl,
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
    file: Path, file_upload_link: Union[FileUploadSchema, MultiPartUploadLinks]
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
                _upload_file_part(
                    session,
                    file,
                    index,
                    index * file_chunk_size,
                    this_file_chunk_size,
                    num_urls,
                    upload_url,
                )
            )
        results = await asyncio.gather(*upload_tasks)
    part_to_etag = [
        UploadedPart(number=index + 1, e_tag=e_tag) for index, e_tag in results
    ]
    print(
        f"--> upload of {file=} of {file_size=} completed in {perf_counter() - start}"
    )
    return part_to_etag
