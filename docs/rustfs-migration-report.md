# Replacing MinIO with RustFS (`s3-storage`)

> Status: **in progress**. Baseline captured; RustFS validation pending (see
> [Benchmark results](#benchmark-results) and [Issues log](#issues--quirks-log)).

## Context & goals

`minio` is the S3 object store used by the osparc-simcore dev/CI stacks (`docker-compose-ops.yml`,
`docker-compose-ops-ci.yml`). MinIO's project pivoted to AGPL-only and has effectively been
deprecated; we want a permissively-licensed, drop-in S3 replacement that is:

1. **100% S3-compatible** — `aws_library.s3.SimcoreS3API` (and therefore all application code)
   must keep working **unchanged** through the swap.
2. **Ideally faster** — especially for the many-small-objects pattern the platform depends on.
3. **Versioned** — bucket object-versioning is load-bearing (see below).
4. **Benchmarked** — a committed before/after harness using our own tooling, not third-party
   load tools.

Selected replacement: **[RustFS](https://rustfs.com/)** (Apache-2.0, Rust, single container),
pinned to `rustfs/rustfs:1.0.0-rc.6`. Fallback if validation fails: SeaweedFS. The compose
service is renamed `minio` → **`s3-storage`** so the stack is backend-agnostic.

Out of scope: the production ops repo (`osparc-ops`), Kubernetes/Helm, and on-disk data
migration (this repo only covers dev + CI).

## Discovery findings

- **Single abstraction point.** Every S3 call goes through
  [`SimcoreS3API`](../packages/aws-library/src/aws_library/s3/_client.py) (aioboto3,
  `signature_version="s3v4"`, custom `endpoint_url`). MinIO is reached only as a plain S3
  endpoint, so the swap is infra + test-harness, **not** application code.
- **S3 operations in use** (all must work in the replacement): `list_buckets`,
  `create_bucket` (+`LocationConstraint`), `head_bucket`, `head_object` (+`ChecksumMode`),
  `list_objects_v2` + paginator, `delete_objects`, `delete_object` (+`VersionId`),
  `list_object_versions`, `generate_presigned_url` (get/put/upload_part),
  `create_multipart_upload`, `list_multipart_uploads`, `abort`/`complete_multipart_upload`,
  `upload_file`/`upload_fileobj`, server-side `copy` (multipart), `get_object` (streaming).
- **Versioning is load-bearing.** `SimcoreS3API.undelete_object()` relies on
  `list_object_versions` + `delete_object(VersionId)` to remove a delete-marker (used by the
  storage service's S3 DSM). No production code calls `put_bucket_versioning` — bucket
  versioning is provisioned by the deployment, so the replacement **must** support it. This is
  gated in the benchmark harness.
- **rclone path.** `settings_library/utils_r_clone.py` maps an `S3Provider` enum to rclone
  config; used by dynamic-sidecar mounts, director-v2, and agent volume backups.
- **Compose.** `docker-compose-ops.yml` and `docker-compose-ops-ci.yml` run MinIO with the API
  port published `9001:9000`; the storage service creates the bucket at runtime (no init
  container).
- **pytest harness** references the service name `"minio"` in
  `pytest_simcore/minio_service.py`, `docker_compose.py`, and ~12
  `pytest_simcore_ops_services_selection` lists.
- **MinIO quirks already coded around:** `list_multipart_uploads` prefix behaviour, and a
  non-JSON error body in `node_ports_common/_file_io_utils.py`.

### rclone provider analysis

rclone's `provider` field selects only *vendor quirks and defaults* (ListObjects version,
path-style, SSE, multipart-ETag handling) — never auth or routing. Verified against
[rclone S3 docs](https://rclone.org/s3/):

- `"Minio"` → MinIO-specific defaults.
- `"Other"` → *"Any other S3 compatible provider"*: generic path-style, `force_path_style`
  defaults true. This is the documented generic choice for a non-AWS, non-MinIO server.
- `AWS_MOTO` already maps to `"Other"` in this repo and works today.

Since RustFS is **not** MinIO, `"Other"` is the semantically correct mapping.

## Design decisions

| Decision | Choice | Rationale |
|---|---|---|
| Replacement | RustFS (`rustfs/rustfs:1.0.0-rc.6`, pinned) | Apache-2.0, single container, faster small objects |
| Fallback | SeaweedFS | mature, full S3 matrix, same enum mapping works |
| Compose service name | `minio` → `s3-storage` | backend-agnostic |
| `S3Provider` enum | **add** `RUSTFS`, **delete** `MINIO` | explicit rename (minio deprecated); pydantic rejects stale `MINIO` = loud migration signal |
| rclone mapping | `S3Provider.RUSTFS` → `{"provider": "Other", "endpoint": "{endpoint}"}` | generic documented mapping |
| Env values | `R_CLONE_PROVIDER` / `AGENT_VOLUMES_CLEANUP_S3_PROVIDER`: `MINIO` → `RUSTFS` | consistency with enum |
| Port | keep `9001:9000` | `S3_ENDPOINT` and every presigned URL stay transparent |
| Benchmark | our own aioboto3 harness (`scripts/s3-benchmark/`) | mirrors `aws_library` config exactly |
| App S3 code | unchanged | abstraction is vendor-agnostic |

## Benchmark methodology

See [`scripts/s3-benchmark/README.md`](../scripts/s3-benchmark/README.md). The harness builds
an aioboto3 client with the **same config as `SimcoreS3API`** and runs seven perf workloads plus
a five-check compatibility gate (versioning, multipart-upload listing, error bodies, checksum
mode, presigned part upload). It exits non-zero if any compat check fails.

Run:

```bash
S3_ENDPOINT=http://127.0.0.1:9001 S3_ACCESS_KEY=... S3_SECRET_KEY=... \
S3_BUCKET_NAME=s3-benchmark \
uv run scripts/s3-benchmark/bench_s3.py --label <label> --json-out <file>
```

## Benchmark results

### Baseline — MinIO `RELEASE.2025-04-22T22-12-26Z`

<sub>localhost, single container, `--small-ops 2000 --concurrency 20 --big-size-mb 64`. Local
loopback numbers, not a production sizing test — the goal is a like-for-like before/after.</sub>

| workload | ops | ops/s | MB/s | p50 ms | p95 ms |
|---|---|---|---|---|---|
| small_put | 2000 | 992.1 | 48.4 | 21.9 | 27.9 |
| small_get | 2000 | 1076.1 | 0.0 | 14.5 | 23.6 |
| multipart | 1 | 2.6 | 167.5 | 0.0 | 0.0 |
| download | 1 | 16.7 | 1071.8 | 59.7 | 59.7 |
| listing | 2000 | 9217.8 | 0.0 | 0.0 | 0.0 |
| copy | 1 | 15.2 | 973.1 | 65.8 | 65.8 |
| presigned | 2 | 48.5 | 48.5 | 41.2 | 41.2 |

Compatibility gate (MinIO): **all PASS**.

### Result — RustFS `1.0.0-rc.6`

_Pending — captured at the validation step._

## Issues & quirks log

- **[MinIO] multipart-upload listing ignores directory prefixes.** Reproduced against the
  baseline: `list_multipart_uploads(Prefix="some/dir/")` returns nothing for an in-flight
  upload, while a full-key prefix matches. This is
  [minio/minio#7632](https://github.com/minio/minio/issues/7632). Platform code
  (`list_ongoing_multipart_uploads`) calls it **without** a prefix (works), so this is
  informational — but it confirms the harness correctly detects vendor divergences. The
  compat check treats no-prefix listing as the hard requirement and reports prefix semantics
  informationally. RustFS claims to fix prefix listing (rustfs#5195); validated at the
  RustFS step.
- **[harness] aioboto3 streaming.** `get_object()["Body"]` must be read directly
  (`await body.read(n)`), not wrapped in `async with` (which yields an aiohttp `ClientResponse`
  whose `read()` takes no size argument). Now matches `aws_library`.
- _RustFS healthcheck path, exact env-var names, and volume permissions (UID 10001) to be
  verified during the compose swap._

## Migration notes for deployers

- `R_CLONE_PROVIDER=MINIO` / `AGENT_VOLUMES_CLEANUP_S3_PROVIDER=MINIO` will be **rejected** by
  pydantic after this change — set them to `RUSTFS`.
- The external `osparc-ops` deployment `.env` must be updated accordingly (out of scope here;
  ops team to be notified).
- Bucket versioning remains provisioned by the deployment; unchanged.

## Summary of changes

_Populated at the final step: commit list + files touched._
