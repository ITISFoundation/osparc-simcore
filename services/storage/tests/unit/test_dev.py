# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from pprint import pprint
from typing import Dict

import aiobotocore


async def test_it(minio_service: Dict, bucket_name: str, faker):

    filename = faker.file_name(extension="bin")
    folder = "test_dev/test_it"
    key_name = f"{folder}/{filename}"

    session = aiobotocore.get_session()
    async with session.create_client(
        service_name="s3",
        endpoint_url=minio_service["url"],
        aws_access_key_id=minio_service["access_key"],
        aws_secret_access_key=minio_service["secret_key"],
    ) as client:
        assert client

        data = b"\x01" * 1024  # 1KB
        resp = await client.put_object(Bucket=bucket_name, Key=key_name, Body=data)
        pprint(resp)

        etag = resp["ETag"]
        meta = resp["ResponseMetadata"]
        # {'ETag': '"54ac58cc1e2711a1a3d88bce15bb152d"',
        # 'ResponseMetadata': {'HTTPHeaders': {'accept-ranges': 'bytes',
        #                                     'content-length': '0',
        #                                     'content-security-policy': 'block-all-mixed-content',
        #                                     'date': 'Wed, 28 Apr 2021 11:38:07 GMT',
        #                                     'etag': '"54ac58cc1e2711a1a3d88bce15bb152d"',
        #                                     'server': 'MinIO',
        #                                     'vary': 'Origin',
        #                                     'x-amz-request-id': '167A029C7DC25169',
        #                                     'x-xss-protection': '1; mode=block'},
        #                     'HTTPStatusCode': 200,
        #                     'HostId': '',
        #                     'RequestId': '167A029C7DC25169',
        #                     'RetryAttempts': 0}}

        resp = await client.list_objects_v2(Bucket=bucket_name, Prefix=folder)
        pprint(resp)

        assert resp["KeyCount"] == 1
        assert resp["Contents"][0]["ETag"] == etag

        # {'Contents': [{'ETag': '"54ac58cc1e2711a1a3d88bce15bb152d"',
        #             'Key': 'aiobotocore/dummy.bin',
        #             'LastModified': datetime.datetime(2021, 4, 28, 11, 33, 44, 169000, tzinfo=tzutc()),
        #             'Owner': {'DisplayName': 'minio',
        #                         'ID': '02d6176db174dc93cb1b899f7c6078f08654445fe8cf1b6ce98d8855f66bdbf4'},
        #             'Size': 1024,
        #             'StorageClass': 'STANDARD'}],
        # 'Delimiter': '',
        # 'EncodingType': 'url',
        # 'IsTruncated': False,
        # 'KeyCount': 1,
        # 'MaxKeys': 4500,
        # 'Name': 'simcore',
        # 'Prefix': 'aiobotocore',
        # 'ResponseMetadata': {'HTTPHeaders': {'accept-ranges': 'bytes',
        #                                     'content-length': '639',
        #                                     'content-security-policy': 'block-all-mixed-content',
        #                                     'content-type': 'application/xml',
        #                                     'date': 'Wed, 28 Apr 2021 11:33:52 GMT',
        #                                     'server': 'MinIO',
        #                                     'vary': 'Origin',
        #                                     'x-amz-request-id': '167A02614131B382',
        #                                     'x-xss-protection': '1; mode=block'},
        #                     'HTTPStatusCode': 200,
        #                     'HostId': '',
        #                     'RequestId': '167A02614131B382',
        #                     'RetryAttempts': 0}}

        # getting s3 object properties of file we just uploaded
        resp = await client.get_object_acl(Bucket=bucket_name, Key=key_name)
        pprint(resp)

        # get object from s3
        response = await client.get_object(Bucket=bucket_name, Key=key_name)
        # this will ensure the connection is correctly re-used/closed
        async with response["Body"] as stream:
            assert await stream.read() == data

        # list s3 objects using paginator
        paginator = client.get_paginator("list_objects")
        async for result in paginator.paginate(Bucket=bucket_name, Prefix=folder):
            for n, c in enumerate(result.get("Contents", [])):
                pprint(f"{n+1}: {c}")

        # delete object from s3
        resp = await client.delete_object(Bucket=bucket_name, Key=key_name)
        pprint(resp)
