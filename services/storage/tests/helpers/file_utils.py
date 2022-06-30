import json
from pathlib import Path
from time import perf_counter
from typing import Final

import aiofiles
import pytest
from aiohttp import ClientSession, web
from pydantic import AnyUrl, ByteSize, parse_obj_as
from simcore_service_storage.s3_client import ETag

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
) -> ETag:
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
    return received_e_tag


async def upload_file_to_presigned_link(file: Path, file_upload_link: AnyUrl) -> ETag:

    file_size = file.stat().st_size

    start = perf_counter()
    print(f"--> uploading {file=}")
    async with ClientSession() as session:
        e_tag = await upload_file_part(
            session,
            file,
            0,
            0,
            file.stat().st_size,
            1,
            file_upload_link,
        )
    print(
        f"--> upload of {file=} of {file_size=} completed in {perf_counter() - start}"
    )
    return e_tag


def parametrized_file_size(size_str: str):
    return pytest.param(parse_obj_as(ByteSize, size_str), id=size_str)
