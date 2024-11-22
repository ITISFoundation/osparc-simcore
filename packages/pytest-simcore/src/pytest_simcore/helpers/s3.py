import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Final

import aiofiles
import orjson
from aiohttp import ClientSession
from aws_library.s3 import MultiPartUploadLinks
from models_library.api_schemas_storage import ETag, FileUploadSchema, UploadedPart
from pydantic import AnyUrl, ByteSize, TypeAdapter
from servicelib.aiohttp import status
from servicelib.utils import limited_as_completed, logged_gather
from types_aiobotocore_s3 import S3Client

from .logging_tools import log_context

_SENDER_CHUNK_SIZE: Final[int] = TypeAdapter(ByteSize).validate_python("16Mib")


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
                msg = "we were asked to raise here!"
                raise RuntimeError(msg)


async def upload_file_part(
    session: ClientSession,
    file: Path,
    part_index: int,
    file_offset: int,
    this_file_chunk_size: int,
    num_parts: int,
    upload_url: AnyUrl,
    *,
    raise_while_uploading: bool = False,
) -> tuple[int, ETag]:
    print(
        f"--> uploading {this_file_chunk_size=} of {file=}, [{part_index+1}/{num_parts}]..."
    )
    response = await session.put(
        str(upload_url),
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
    assert response.status == status.HTTP_200_OK
    assert response.headers
    assert "Etag" in response.headers
    received_e_tag = orjson.loads(response.headers["Etag"])
    print(
        f"--> completed upload {this_file_chunk_size=} of {file=}, [{part_index+1}/{num_parts}], {received_e_tag=}"
    )
    return (part_index, received_e_tag)


async def upload_file_to_presigned_link(
    file: Path, file_upload_link: FileUploadSchema | MultiPartUploadLinks
) -> list[UploadedPart]:
    file_size = file.stat().st_size

    with log_context(logging.INFO, msg=f"uploading {file} via {file_upload_link=}"):
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
            results = await logged_gather(*upload_tasks, max_concurrency=0)
        return [UploadedPart(number=index + 1, e_tag=e_tag) for index, e_tag in results]


async def delete_all_object_versions(
    s3_client: S3Client, bucket: str, keys: Iterable[str]
) -> None:
    objects_to_delete = []

    bucket_versioning = await s3_client.get_bucket_versioning(Bucket=bucket)
    if "Status" in bucket_versioning and bucket_versioning["Status"] == "Enabled":
        # NOTE: using gather here kills the moto server
        all_versions = [
            await v
            async for v in limited_as_completed(
                (
                    s3_client.list_object_versions(Bucket=bucket, Prefix=key)
                    for key in keys
                ),
                limit=10,
            )
        ]

        for versions in all_versions:
            # Collect all version IDs and delete markers
            objects_to_delete.extend(
                {"Key": version["Key"], "VersionId": version["VersionId"]}
                for version in versions.get("Versions", [])
            )

            objects_to_delete.extend(
                {"Key": marker["Key"], "VersionId": marker["VersionId"]}
                for marker in versions.get("DeleteMarkers", [])
            )
    else:
        # NOTE: this is way faster
        objects_to_delete = [{"Key": key} for key in keys]
    # Delete all versions and delete markers
    if objects_to_delete:
        await s3_client.delete_objects(
            Bucket=bucket, Delete={"Objects": objects_to_delete}
        )
