import datetime
import json
import logging
import urllib.parse
from contextlib import AsyncExitStack
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, cast

import aioboto3
from aiobotocore.session import ClientCreatorContext
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from models_library.api_schemas_storage import UploadedPart
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID, SimcoreS3FileID
from pydantic import AnyUrl, ByteSize, parse_obj_as
from servicelib.utils import logged_gather
from settings_library.s3 import S3Settings
from simcore_service_storage.constants import MULTIPART_UPLOADS_MIN_TOTAL_SIZE
from types_aiobotocore_s3 import S3Client

from .models import ETag, MultiPartUploadLinks, S3BucketName, UploadID
from .s3_utils import compute_num_file_chunks, s3_exception_handler

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class S3MetaData:
    file_id: SimcoreS3FileID
    last_modified: datetime.datetime
    e_tag: ETag
    size: int


@dataclass
class StorageS3Client:
    session: aioboto3.Session
    client: S3Client
    transfer_max_concurrency: int

    @classmethod
    async def create(
        cls, exit_stack: AsyncExitStack, settings: S3Settings, s3_max_concurrency: int
    ) -> "StorageS3Client":
        # upon creation the client does not try to connect, one need to make an operation
        session = aioboto3.Session()
        # NOTE: session.client returns an aiobotocore client enhanced with aioboto3 fcts (e.g. download_file, upload_file, copy_file...)
        session_client = session.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            aws_session_token=settings.S3_ACCESS_TOKEN,
            region_name=settings.S3_REGION,
            config=Config(signature_version="s3v4"),
        )
        assert isinstance(session_client, ClientCreatorContext)  # nosec
        client = cast(S3Client, await exit_stack.enter_async_context(session_client))
        # NOTE: this triggers a botocore.exception.ClientError in case the connection is not made to the S3 backend
        await client.list_buckets()

        return cls(session, client, s3_max_concurrency)

    @s3_exception_handler(log)
    async def create_bucket(self, bucket: S3BucketName) -> None:
        log.debug("Creating bucket: %s", bucket)
        try:
            await self.client.create_bucket(Bucket=bucket)
            log.info("Bucket %s successfully created", bucket)
        except self.client.exceptions.BucketAlreadyOwnedByYou:
            log.info(
                "Bucket %s already exists and is owned by us",
                bucket,
            )

    @s3_exception_handler(log)
    async def check_bucket_connection(self, bucket: S3BucketName) -> None:
        """
        :raises: S3BucketInvalidError if not existing, not enough rights
        :raises: S3AccessError for any other error
        """
        log.debug("Head bucket: %s", bucket)
        await self.client.head_bucket(Bucket=bucket)

    @s3_exception_handler(log)
    async def create_single_presigned_download_link(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID, expiration_secs: int
    ) -> AnyUrl:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self.client.head_bucket(Bucket=bucket)
        await self.get_file_metadata(bucket, file_id)
        generated_link = await self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": file_id},
            ExpiresIn=expiration_secs,
        )
        return parse_obj_as(AnyUrl, generated_link)

    @s3_exception_handler(log)
    async def create_single_presigned_upload_link(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID, expiration_secs: int
    ) -> AnyUrl:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self.client.head_bucket(Bucket=bucket)
        generated_link = await self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": file_id},
            ExpiresIn=expiration_secs,
        )
        return parse_obj_as(AnyUrl, generated_link)

    @s3_exception_handler(log)
    async def create_multipart_upload_links(
        self,
        bucket: S3BucketName,
        file_id: SimcoreS3FileID,
        file_size: ByteSize,
        expiration_secs: int,
    ) -> MultiPartUploadLinks:
        # NOTE: ensure the bucket/object exists, this will raise if not
        await self.client.head_bucket(Bucket=bucket)
        # first initiate the multipart upload
        response = await self.client.create_multipart_upload(Bucket=bucket, Key=file_id)
        upload_id = response["UploadId"]
        # compute the number of links, based on the announced file size
        num_upload_links, chunk_size = compute_num_file_chunks(file_size)
        # now create the links
        upload_links = parse_obj_as(
            list[AnyUrl],
            await logged_gather(
                *[
                    self.client.generate_presigned_url(
                        "upload_part",
                        Params={
                            "Bucket": bucket,
                            "Key": file_id,
                            "PartNumber": i + 1,
                            "UploadId": upload_id,
                        },
                        ExpiresIn=expiration_secs,
                    )
                    for i in range(num_upload_links)
                ],
                log=log,
                max_concurrency=20,
            ),
        )
        return MultiPartUploadLinks(
            upload_id=upload_id, chunk_size=chunk_size, urls=upload_links
        )

    @s3_exception_handler(log)
    async def list_ongoing_multipart_uploads(
        self,
        bucket: S3BucketName,
    ) -> list[tuple[UploadID, SimcoreS3FileID]]:
        """Returns all the currently ongoing multipart uploads

        NOTE: minio does not implement the same behaviour as AWS here and will
        only return the uploads if a prefix or object name is given [minio issue](https://github.com/minio/minio/issues/7632).

        :return: list of AWS uploads see [boto3 documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.list_multipart_uploads)
        """
        response = await self.client.list_multipart_uploads(
            Bucket=bucket,
        )

        return [
            (
                upload.get("UploadId", "undefined-uploadid"),
                SimcoreS3FileID(upload.get("Key", "undefined-key")),
            )
            for upload in response.get("Uploads", [])
        ]

    @s3_exception_handler(log)
    async def abort_multipart_upload(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID, upload_id: UploadID
    ) -> None:
        await self.client.abort_multipart_upload(
            Bucket=bucket, Key=file_id, UploadId=upload_id
        )

    @s3_exception_handler(log)
    async def complete_multipart_upload(
        self,
        bucket: S3BucketName,
        file_id: SimcoreS3FileID,
        upload_id: UploadID,
        uploaded_parts: list[UploadedPart],
    ) -> ETag:
        response = await self.client.complete_multipart_upload(
            Bucket=bucket,
            Key=file_id,
            UploadId=upload_id,
            MultipartUpload={
                "Parts": [
                    {"ETag": part.e_tag, "PartNumber": part.number}
                    for part in uploaded_parts
                ]
            },
        )
        return response["ETag"]

    @s3_exception_handler(log)
    async def delete_file(self, bucket: S3BucketName, file_id: SimcoreS3FileID) -> None:
        await self.client.delete_object(Bucket=bucket, Key=file_id)

    @s3_exception_handler(log)
    async def delete_files_in_project_node(
        self,
        bucket: S3BucketName,
        project_id: ProjectID,
        node_id: Optional[NodeID] = None,
    ) -> None:
        # NOTE: the / at the end of the Prefix is VERY important,
        # makes the listing several order of magnitudes faster
        response = await self.client.list_objects_v2(
            Bucket=bucket,
            Prefix=f"{project_id}/{node_id}/" if node_id else f"{project_id}/",
        )

        if objects_to_delete := [
            f["Key"] for f in response.get("Contents", []) if "Key" in f
        ]:
            await self.client.delete_objects(
                Bucket=bucket,
                Delete={"Objects": [{"Key": key} for key in objects_to_delete]},
            )

    @s3_exception_handler(log)
    async def get_file_metadata(
        self, bucket: S3BucketName, file_id: SimcoreS3FileID
    ) -> S3MetaData:
        response = await self.client.head_object(Bucket=bucket, Key=file_id)
        return S3MetaData(
            file_id=file_id,
            last_modified=response["LastModified"],
            e_tag=json.loads(response["ETag"]),
            size=response["ContentLength"],
        )

    @s3_exception_handler(log)
    async def copy_file(
        self,
        bucket: S3BucketName,
        src_file: SimcoreS3FileID,
        dst_file: SimcoreS3FileID,
        bytes_transfered_cb: Optional[Callable[[int], None]],
    ) -> None:
        """copy a file in S3 using aioboto3 transfer manager (e.g. works >5Gb and creates multiple threads)

        :type bucket: S3BucketName
        :type src_file: SimcoreS3FileID
        :type dst_file: SimcoreS3FileID
        """
        copy_options = dict(
            CopySource={"Bucket": bucket, "Key": src_file},
            Bucket=bucket,
            Key=dst_file,
            Config=TransferConfig(max_concurrency=self.transfer_max_concurrency),
        )
        if bytes_transfered_cb:
            copy_options |= dict(Callback=bytes_transfered_cb)
        await self.client.copy(**copy_options)

    @s3_exception_handler(log)
    async def list_files(
        self, bucket: S3BucketName, *, prefix: str
    ) -> list[S3MetaData]:
        # NOTE: adding a / at the end of a folder improves speed by several orders of magnitudes
        response = await self.client.list_objects_v2(Bucket=bucket, Prefix=prefix)
        return [
            S3MetaData(
                file_id=entry["Key"],  # type: ignore
                last_modified=entry["LastModified"],  # type: ignore
                e_tag=json.loads(entry["ETag"]),  # type: ignore
                size=entry["Size"],  # type: ignore
            )
            for entry in response.get("Contents", [])
            if all(k in entry for k in ("Key", "LastModified", "ETag", "Size"))
        ]

    @s3_exception_handler(log)
    async def upload_file(
        self,
        bucket: S3BucketName,
        file: Path,
        file_id: SimcoreS3FileID,
        bytes_transfered_cb: Optional[Callable[[int], None]],
    ) -> None:
        """upload a file using aioboto3 transfer manager (e.g. works >5Gb and create multiple threads)

        :type bucket: S3BucketName
        :type file: Path
        :type file_id: SimcoreS3FileID
        """
        upload_options = dict(
            Bucket=bucket,
            Key=file_id,
            Config=TransferConfig(max_concurrency=self.transfer_max_concurrency),
        )
        if bytes_transfered_cb:
            upload_options |= dict(Callback=bytes_transfered_cb)
        await self.client.upload_file(f"{file}", **upload_options)

    @staticmethod
    def compute_s3_url(bucket: S3BucketName, file_id: SimcoreS3FileID) -> AnyUrl:
        return parse_obj_as(AnyUrl, f"s3://{bucket}/{urllib.parse.quote(file_id)}")

    @staticmethod
    def is_multipart(file_size: ByteSize) -> bool:
        return file_size >= MULTIPART_UPLOADS_MIN_TOTAL_SIZE
