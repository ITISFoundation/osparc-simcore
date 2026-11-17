#!/usr/bin/env python3
# ruff: noqa: T201, FBT003, PLR2004, PERF401
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "aioboto3",
#     "httpx",
# ]
# ///
"""S3 benchmark and compatibility harness for the MinIO -> RustFS migration.

Configured exactly like aws_library.s3.SimcoreS3API (aioboto3 + SigV4 +
custom endpoint) so results reflect what the platform actually experiences.

Environment variables (same names as the platform settings):
    S3_ENDPOINT     e.g. http://172.17.0.1:9001
    S3_ACCESS_KEY
    S3_SECRET_KEY
    S3_REGION       default us-east-1
    S3_BUCKET_NAME  benchmark bucket (created if missing), default s3-benchmark

Usage:
    python bench_s3.py --label minio-baseline [--keep] [--json-out results.json]

Workloads (perf):
    small_put  small-object PUTs (concurrent)
    small_get  small-object GETs (concurrent)
    multipart  large-object multipart upload (TransferConfig, 8 MiB parts)
    download   large-object download
    listing    list_objects_v2 pagination over N keys
    copy       server-side copy of a large object (multipart copy)
    presigned  presigned PUT/GET round trip

Workloads (compat gate, must all pass on any S3 replacement):
    versioning          put x2 -> delete -> list_object_versions -> remove delete marker
                        (mirrors SimcoreS3API.undelete_object)
    multipart_listing   list_multipart_uploads (no prefix, as aws-library calls it)
                        + list_parts; prefix semantics reported informationally
                        (MinIO #7632: only full-key prefixes match)
    error_body          error responses yield non-JSON bodies without raising
                        in the client layer (file_io_utils.py quirk)
"""

import argparse
import asyncio
import contextlib
import io
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Self

import aioboto3
import httpx
from aiobotocore.session import ClientCreatorContext
from boto3.s3.transfer import TransferConfig
from botocore.client import Config
from botocore.exceptions import ClientError

# --- mirrors aws_library/s3/_client.py -----------------------------------------
DEFAULT_REGION = "us-east-1"
MULTIPART_UPLOADS_MIN_TOTAL_SIZE = 16 * 1024 * 1024  # 16 MiB (same as aws-library)

_BENCH_PREFIX = "s3-benchmark"


@dataclass
class WorkloadResult:
    name: str
    ops: int = 0
    bytes_total: int = 0
    duration_s: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)
    error: str | None = None

    @property
    def ops_per_s(self) -> float:
        return self.ops / self.duration_s if self.duration_s > 0 else 0.0

    @property
    def mb_per_s(self) -> float:
        return (self.bytes_total / 1024 / 1024) / self.duration_s if self.duration_s > 0 else 0.0

    def percentile(self, p: float) -> float:
        if not self.latencies_ms:
            return 0.0
        ordered = sorted(self.latencies_ms)
        idx = min(len(ordered) - 1, int(len(ordered) * p))
        return ordered[idx]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ops": self.ops,
            "bytes_total": self.bytes_total,
            "duration_s": round(self.duration_s, 3),
            "ops_per_s": round(self.ops_per_s, 2),
            "mb_per_s": round(self.mb_per_s, 2),
            "p50_ms": round(self.percentile(0.50), 2),
            "p95_ms": round(self.percentile(0.95), 2),
            "error": self.error,
        }


@dataclass
class CompatResult:
    name: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail}


class Timed:
    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def __enter__(self) -> Self:
        self._t0 = time.perf_counter()
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    @property
    def elapsed(self) -> float:
        return time.perf_counter() - self._t0


async def _create_client(session: aioboto3.Session, settings: dict[str, str]):
    config = Config(
        signature_version="s3v4",
        request_checksum_calculation="when_required",
    )
    ctx = session.client(
        "s3",
        endpoint_url=settings["S3_ENDPOINT"],
        aws_access_key_id=settings["S3_ACCESS_KEY"],
        aws_secret_access_key=settings["S3_SECRET_KEY"],
        region_name=settings.get("S3_REGION", DEFAULT_REGION),
        config=config,
    )
    assert isinstance(ctx, ClientCreatorContext)
    return ctx


async def ensure_bucket(client, bucket: str, region: str) -> None:
    create_kwargs: dict[str, Any] = {"Bucket": bucket}
    if region != DEFAULT_REGION:
        create_kwargs["CreateBucketConfiguration"] = {"LocationConstraint": region}
    with contextlib.suppress(client.exceptions.BucketAlreadyOwnedByYou):
        await client.create_bucket(**create_kwargs)


def _key(suffix: str) -> str:
    return f"{_BENCH_PREFIX}/{suffix}"


async def _enable_versioning(client, bucket: str) -> bool:
    """Best-effort bucket versioning enable for the compat gate."""
    try:
        await client.put_bucket_versioning(Bucket=bucket, VersioningConfiguration={"Status": "Enabled"})
        return True
    except Exception as exc:
        print(f"  ! put_bucket_versioning failed: {exc}", file=sys.stderr)
        return False


# --- perf workloads -----------------------------------------------------------


async def wl_small_put(client, bucket: str, *, n_ops: int, size_bytes: int, concurrency: int) -> WorkloadResult:
    result = WorkloadResult(name="small_put")
    data = os.urandom(size_bytes)
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(i: int) -> None:
        async with semaphore:
            timed = Timed()
            await client.put_object(Bucket=bucket, Key=_key(f"small/{i}"), Body=data)
            result.latencies_ms.append(timed.elapsed * 1000)
            result.ops += 1
            result.bytes_total += size_bytes

    with Timed() as total:
        await asyncio.gather(*(_one(i) for i in range(n_ops)))
    result.duration_s = total.elapsed
    return result


async def wl_small_get(client, bucket: str, *, n_ops: int, concurrency: int) -> WorkloadResult:
    result = WorkloadResult(name="small_get")
    semaphore = asyncio.Semaphore(concurrency)

    async def _one(i: int) -> None:
        async with semaphore:
            timed = Timed()
            resp = await client.get_object(Bucket=bucket, Key=_key(f"small/{i}"))
            async with resp["Body"] as stream:
                await stream.read()
            result.latencies_ms.append(timed.elapsed * 1000)
            result.ops += 1

    with Timed() as total:
        await asyncio.gather(*(_one(i) for i in range(n_ops)))
    result.duration_s = total.elapsed
    return result


async def wl_multipart_upload(client, bucket: str, *, size_mb: int, part_mb: int, concurrency: int) -> WorkloadResult:
    result = WorkloadResult(name="multipart")
    data = os.urandom(size_mb * 1024 * 1024)
    transfer_config = TransferConfig(
        multipart_threshold=MULTIPART_UPLOADS_MIN_TOTAL_SIZE,
        multipart_chunksize=part_mb * 1024 * 1024,
        max_concurrency=concurrency,
    )
    timed = Timed()
    # same path aws_library uses for streams (SimcoreS3API._upload_stream ->
    # client.upload_fileobj), which triggers managed multipart above the threshold
    await client.upload_fileobj(  # type: ignore[attr-defined]
        io.BytesIO(data),
        bucket,
        _key("big/multipart.bin"),
        Config=transfer_config,
    )
    result.duration_s = timed.elapsed
    result.ops = 1
    result.bytes_total = len(data)
    return result


async def wl_download(client, bucket: str) -> WorkloadResult:
    result = WorkloadResult(name="download")
    timed = Timed()
    resp = await client.get_object(Bucket=bucket, Key=_key("big/multipart.bin"))
    total_bytes = 0
    body = resp["Body"]  # same pattern as SimcoreS3API.get_object (aws_library)
    while chunk := await body.read(1024 * 1024):
        total_bytes += len(chunk)
    result.duration_s = timed.elapsed
    result.ops = 1
    result.bytes_total = total_bytes
    result.latencies_ms.append(result.duration_s * 1000)
    return result


async def wl_listing(client, bucket: str, *, n_keys: int) -> WorkloadResult:
    result = WorkloadResult(name="listing")
    # keys already uploaded by small_put (n_ops should equal n_keys ideally);
    # additionally ensure enough keys exist
    with Timed() as total:
        paginator = client.get_paginator("list_objects_v2")
        count = 0
        async for page in paginator.paginate(Bucket=bucket, Prefix=f"{_BENCH_PREFIX}/small/"):
            count += page.get("KeyCount", 0)
    result.duration_s = total.elapsed
    result.ops = count
    result.bytes_total = 0
    print(f"    listed {count} keys (requested ~{n_keys})")
    return result


async def wl_server_side_copy(client, bucket: str) -> WorkloadResult:
    result = WorkloadResult(name="copy")
    timed = Timed()
    # copy above the multipart copy threshold triggers multipart copy internally
    copy_source = {"Bucket": bucket, "Key": _key("big/multipart.bin")}
    await client.copy(copy_source, bucket, _key("big/multipart-copy.bin"))  # type: ignore[attr-defined]
    resp = await client.head_object(Bucket=bucket, Key=_key("big/multipart-copy.bin"))
    result.duration_s = timed.elapsed
    result.ops = 1
    result.bytes_total = resp["ContentLength"]
    result.latencies_ms.append(result.duration_s * 1000)
    return result


async def wl_presigned(client, bucket: str, *, size_bytes: int) -> WorkloadResult:
    result = WorkloadResult(name="presigned")
    key = _key("presigned/roundtrip.bin")
    data = os.urandom(size_bytes)
    latencies: list[float] = []

    timed = Timed()
    put_url = await client.generate_presigned_url("put_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=60)
    async with httpx.AsyncClient() as http:
        r = await http.put(put_url, content=data, headers={"Content-Type": "application/octet-stream"})
        r.raise_for_status()
        get_url = await client.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": key}, ExpiresIn=60)
        r = await http.get(get_url)
        r.raise_for_status()
        assert r.content == data
    latencies.append(timed.elapsed * 1000)
    result.duration_s = timed.elapsed
    result.ops = 2  # put + get
    result.bytes_total = 2 * size_bytes
    result.latencies_ms = latencies
    return result


# --- compat gate ---------------------------------------------------------------


async def compat_versioning(client, bucket: str) -> CompatResult:
    """Mirrors SimcoreS3API.undelete_object: list_object_versions + delete_object(VersionId)."""
    key = _key("compat/versioned.txt")
    try:
        enabled = await _enable_versioning(client, bucket)
        if not enabled:
            return CompatResult("versioning", False, "could not enable bucket versioning")

        await client.put_object(Bucket=bucket, Key=key, Body=b"v1")
        await client.put_object(Bucket=bucket, Key=key, Body=b"v2")
        await client.delete_object(Bucket=bucket, Key=key)  # creates delete marker

        response = await client.list_object_versions(Bucket=bucket, Prefix=key)
        versions = response.get("Versions", [])
        markers = response.get("DeleteMarkers", [])
        if len(versions) < 2 or not markers:
            return CompatResult(
                "versioning",
                False,
                f"versions={len(versions)} markers={len(markers)} (expected >=2 versions + >=1 marker)",
            )
        # remove the latest delete marker -> object "undeleted"
        latest_marker = max(markers, key=lambda m: m["LastModified"])
        await client.delete_object(Bucket=bucket, Key=key, VersionId=latest_marker["VersionId"])

        got = await client.get_object(Bucket=bucket, Key=key)
        async with got["Body"] as stream:
            body = await stream.read()
        if body != b"v2":
            return CompatResult("versioning", False, f"undeleted content mismatch: {body!r}")
        return CompatResult("versioning", True, "put x2, delete, list versions, remove marker OK")
    except Exception as exc:
        return CompatResult("versioning", False, f"{type(exc).__name__}: {exc}")


async def compat_multipart_listing(client, bucket: str) -> CompatResult:
    key = _key("compat/multipart-listing.bin")
    upload_id: str | None = None
    try:
        part_size = 16 * 1024 * 1024
        mpu = await client.create_multipart_upload(Bucket=bucket, Key=key)
        upload_id = mpu["UploadId"]
        await client.upload_part(Bucket=bucket, Key=key, PartNumber=1, UploadId=upload_id, Body=os.urandom(part_size))

        # aws_library.list_ongoing_multipart_uploads calls WITHOUT prefix -> hard requirement
        listed = await client.list_multipart_uploads(Bucket=bucket)
        ids = [u["UploadId"] for u in listed.get("Uploads", [])]
        if upload_id not in ids:
            return CompatResult("multipart_listing", False, "in-flight upload missing from list_multipart_uploads()")

        # informational: prefix semantics (MinIO #7632: directory prefixes do not match,
        # only full-key prefixes do; AWS-correct servers match both; RustFS #5195 claims fix)
        r_dir = await client.list_multipart_uploads(Bucket=bucket, Prefix=f"{_BENCH_PREFIX}/compat/")
        r_key = await client.list_multipart_uploads(Bucket=bucket, Prefix=key)
        dir_ok = upload_id in [u["UploadId"] for u in r_dir.get("Uploads", [])]
        key_ok = upload_id in [u["UploadId"] for u in r_key.get("Uploads", [])]
        prefix_detail = f"dir_prefix_match={dir_ok} full_key_prefix_match={key_ok}"

        # list parts must work too
        parts = await client.list_parts(Bucket=bucket, Key=key, UploadId=upload_id)
        if not parts.get("Parts"):
            return CompatResult("multipart_listing", False, "list_parts returned no parts")

        await client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)
        upload_id = None
        return CompatResult("multipart_listing", True, f"no-prefix list + list_parts OK; {prefix_detail}")
    except Exception as exc:
        return CompatResult("multipart_listing", False, f"{type(exc).__name__}: {exc}")
    finally:
        if upload_id:
            with contextlib.suppress(Exception):
                await client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)


async def compat_error_body(client, bucket: str) -> CompatResult:
    """Get a missing key: botocore must raise ClientError with a usable Code."""
    try:
        await client.get_object(Bucket=bucket, Key=_key("compat/definitely-missing"))
        return CompatResult("error_body", False, "expected ClientError for missing key")
    except ClientError as exc:
        code = exc.response.get("Error", {}).get("Code", "")
        if code in {"404", "NoSuchKey"}:
            return CompatResult("error_body", True, f"ClientError Code={code}")
        return CompatResult("error_body", False, f"unexpected error code: {code!r}")
    except Exception as exc:
        return CompatResult("error_body", False, f"{type(exc).__name__}: {exc}")


async def compat_checksum_mode(client, bucket: str) -> CompatResult:
    """head_object with ChecksumMode=ENABLED (used by get_object_metadata)."""
    key = _key("compat/checksum.txt")
    try:
        await client.put_object(
            Bucket=bucket,
            Key=key,
            Body=b"checksum-probe",
            ChecksumAlgorithm="SHA256",  # type: ignore[arg-type]
        )
        resp = await client.head_object(Bucket=bucket, Key=key, ChecksumMode="ENABLED")
        ok = bool(resp.get("ChecksumSHA256"))
        return CompatResult(
            "checksum_mode", ok, "ChecksumSHA256 present" if ok else f"no checksum in response: keys={sorted(resp)}"
        )
    except Exception as exc:
        return CompatResult("checksum_mode", False, f"{type(exc).__name__}: {exc}")


async def compat_presigned_multipart_part(client, bucket: str) -> CompatResult:
    """Presigned upload_part URL (dynamic-sidecar uses these)."""
    key = _key("compat/presigned-part.bin")
    upload_id: str | None = None
    try:
        mpu = await client.create_multipart_upload(Bucket=bucket, Key=key)
        upload_id = mpu["UploadId"]
        url = await client.generate_presigned_url(
            "upload_part",
            Params={"Bucket": bucket, "Key": key, "PartNumber": 1, "UploadId": upload_id},
            ExpiresIn=60,
        )
        async with httpx.AsyncClient() as http:
            r = await http.put(url, content=os.urandom(1024 * 1024))
        if r.status_code != 200:
            return CompatResult("presigned_part", False, f"PUT status {r.status_code}: {r.text[:200]}")
        return CompatResult("presigned_part", True, "presigned upload_part OK")
    except Exception as exc:
        return CompatResult("presigned_part", False, f"{type(exc).__name__}: {exc}")
    finally:
        if upload_id:
            with contextlib.suppress(Exception):
                await client.abort_multipart_upload(Bucket=bucket, Key=key, UploadId=upload_id)


# --- cleanup ------------------------------------------------------------------


async def purge(client, bucket: str) -> None:
    paginator = client.get_paginator("list_objects_v2")
    to_delete: list[dict[str, str]] = []
    async for page in paginator.paginate(Bucket=bucket, Prefix=f"{_BENCH_PREFIX}/"):
        for obj in page.get("Contents", []):
            to_delete.append({"Key": obj["Key"]})
        while len(to_delete) >= 1000:
            batch, to_delete = to_delete[:1000], to_delete[1000:]
            await client.delete_objects(Bucket=bucket, Delete={"Objects": batch})
    if to_delete:
        await client.delete_objects(Bucket=bucket, Delete={"Objects": to_delete})

    # remove all versions/markers as well
    resp = await client.list_object_versions(Bucket=bucket, Prefix=f"{_BENCH_PREFIX}/")
    versions = [{"Key": v["Key"], "VersionId": v["VersionId"]} for v in resp.get("Versions", [])] + [
        {"Key": m["Key"], "VersionId": m["VersionId"]} for m in resp.get("DeleteMarkers", [])
    ]
    while len(versions) >= 1000:
        batch, versions = versions[:1000], versions[1000:]
        await client.delete_objects(Bucket=bucket, Delete={"Objects": batch, "Quiet": True})
    if versions:
        await client.delete_objects(Bucket=bucket, Delete={"Objects": versions, "Quiet": True})


# --- main ---------------------------------------------------------------------


def _markdown_table(workloads: list[WorkloadResult], compat: list[CompatResult]) -> str:
    lines = [
        "| workload | ops | ops/s | MB/s | p50 ms | p95 ms |",
        "|---|---|---|---|---|---|",
    ]
    for w in workloads:
        lines.append(
            f"| {w.name} | {w.ops} | {w.ops_per_s:.1f} | {w.mb_per_s:.1f} | "
            f"{w.percentile(0.5):.1f} | {w.percentile(0.95):.1f} |"
        )
    lines += ["", "| compat check | passed | detail |", "|---|---|---|"]
    for c in compat:
        lines.append(f"| {c.name} | {'PASS' if c.passed else 'FAIL'} | {c.detail} |")
    return "\n".join(lines)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", default="run", help="label for this run (e.g. minio-baseline)")
    parser.add_argument("--json-out", type=Path, default=None, help="write JSON results to file")
    parser.add_argument("--small-ops", type=int, default=2000)
    parser.add_argument("--small-size-kb", type=int, default=50)
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--big-size-mb", type=int, default=64)
    parser.add_argument("--part-size-mb", type=int, default=8)
    parser.add_argument("--keep", action="store_true", help="keep benchmark objects")
    args = parser.parse_args()

    settings = {
        "S3_ENDPOINT": os.environ.get("S3_ENDPOINT", "http://172.17.0.1:9001"),
        "S3_ACCESS_KEY": os.environ.get("S3_ACCESS_KEY", ""),
        "S3_SECRET_KEY": os.environ.get("S3_SECRET_KEY", ""),
        "S3_REGION": os.environ.get("S3_REGION", DEFAULT_REGION),
    }
    bucket = os.environ.get("S3_BUCKET_NAME", "s3-benchmark")
    if not settings["S3_ACCESS_KEY"] or not settings["S3_SECRET_KEY"]:
        print("ERROR: S3_ACCESS_KEY and S3_SECRET_KEY must be set", file=sys.stderr)
        return 2

    session = aioboto3.Session()
    workloads: list[WorkloadResult] = []
    compat: list[CompatResult] = []

    async with await _create_client(session, settings) as client:
        await ensure_bucket(client, bucket, settings["S3_REGION"])
        print(f"target: {settings['S3_ENDPOINT']} bucket={bucket} label={args.label}")

        print("[1/7] small put")
        workloads.append(
            await wl_small_put(
                client,
                bucket,
                n_ops=args.small_ops,
                size_bytes=args.small_size_kb * 1024,
                concurrency=args.concurrency,
            )
        )
        print("[2/7] small get")
        workloads.append(await wl_small_get(client, bucket, n_ops=args.small_ops, concurrency=args.concurrency))
        print("[3/7] multipart upload")
        workloads.append(
            await wl_multipart_upload(
                client,
                bucket,
                size_mb=args.big_size_mb,
                part_mb=args.part_size_mb,
                concurrency=args.concurrency,
            )
        )
        print("[4/7] download")
        workloads.append(await wl_download(client, bucket))
        print("[5/7] listing")
        workloads.append(await wl_listing(client, bucket, n_keys=args.small_ops))
        print("[6/7] server-side copy")
        workloads.append(await wl_server_side_copy(client, bucket))
        print("[7/7] presigned round trip")
        workloads.append(await wl_presigned(client, bucket, size_bytes=1024 * 1024))

        print("compat gate:")
        compat.append(await compat_versioning(client, bucket))
        compat.append(await compat_multipart_listing(client, bucket))
        compat.append(await compat_error_body(client, bucket))
        compat.append(await compat_checksum_mode(client, bucket))
        compat.append(await compat_presigned_multipart_part(client, bucket))

        if not args.keep:
            print("cleaning up benchmark objects")
            await purge(client, bucket)

    report = {
        "label": args.label,
        "target": settings["S3_ENDPOINT"],
        "bucket": bucket,
        "workloads": [w.to_dict() for w in workloads],
        "compat": [c.to_dict() for c in compat],
    }
    print()
    print(_markdown_table(workloads, compat))
    if args.json_out:
        args.json_out.write_text(json.dumps(report, indent=2))
        print(f"\nwrote {args.json_out}")

    return 0 if all(c.passed for c in compat) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
