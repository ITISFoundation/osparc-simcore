# S3 benchmark & compatibility harness

Standalone harness used to compare S3 backends (MinIO baseline vs RustFS candidate)
for the storage-service backend swap.

The client is configured **exactly** like `aws_library.s3.SimcoreS3API`
(aioboto3, `signature_version="s3v4"`, `request_checksum_calculation="when_required"`,
custom `endpoint_url`), so numbers reflect what the platform actually experiences.

## Run

```bash
S3_ENDPOINT=http://172.17.0.1:9001 \
S3_ACCESS_KEY=... S3_SECRET_KEY=... \
S3_BUCKET_NAME=s3-benchmark \
uv run bench_s3.py --label minio-baseline --json-out results-minio-baseline.json
```

`uv run` resolves the script's PEP 723 dependencies (`aioboto3`, `httpx`) automatically.

Tuning flags: `--small-ops`, `--small-size-kb`, `--concurrency`, `--big-size-mb`,
`--part-size-mb`, `--keep` (skip cleanup). Exit code is non-zero if any compat check fails.

## Perf workloads

| workload | what it measures |
|---|---|
| small_put / small_get | concurrent 50 KB object PUT/GET (the platform's dominant pattern) |
| multipart | large-object managed multipart upload (`upload_fileobj`, 8 MiB parts) |
| download | large-object streaming download |
| listing | `list_objects_v2` pagination over the small objects |
| copy | server-side (multipart) copy |
| presigned | presigned PUT + GET round trip via plain HTTP |

## Compatibility gate (must PASS on any replacement)

| check | platform dependency |
|---|---|
| versioning | `SimcoreS3API.undelete_object`: `list_object_versions` + `delete_object(VersionId)` (delete-marker removal) |
| multipart_listing | `list_ongoing_multipart_uploads` (no prefix) + `list_parts`; prefix semantics reported informationally (MinIO #7632) |
| error_body | `ClientError` with `NoSuchKey` on missing keys (`file_io_utils` quirk handling) |
| checksum_mode | `head_object(ChecksumMode="ENABLED")` returns `ChecksumSHA256` |
| presigned_part | presigned `upload_part` URL (dynamic-sidecar upload path) |

## Results

- `results-minio-baseline.json` — MinIO `RELEASE.2025-04-22T22-12-26Z` baseline
- `results-rustfs.json` — RustFS candidate (see `docs/rustfs-migration-report.md` for comparison)
