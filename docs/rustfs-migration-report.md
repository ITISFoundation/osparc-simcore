# Replacing MinIO with RustFS (`s3-storage`)

> Status: **complete**. MinIO baseline and RustFS results captured; all compatibility
> checks green on both. See [Benchmark results](#benchmark-results),
> [Issues log](#issues--quirks-log) and [Summary of changes](#summary-of-changes).

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

<sub>Same machine/flags as the baseline; numbers from `--label rustfs-1.0.0-rc.6`
(a second run reproduced them within run-to-run noise).</sub>

| workload | MinIO ops/s | RustFS ops/s | Δ | MinIO MB/s | RustFS MB/s |
|---|---|---|---|---|---|
| small_put | 992.1 | 938.3 | -5% | 48.4 | 45.8 |
| small_get | 1076.1 | 1116.7 | +4% | — | — |
| multipart | 2.6 | 2.3 | -12% | 167.5 | 146.6 |
| download | 16.7 | 17.1 | +2% | 1071.8 | 1097.0 |
| listing | 9217.8 | 1252.1 | **-86%** | — | — |
| copy | 15.2 | 7.6 | **-50%** | 973.1 | 488.4 |
| presigned | 48.5 | 35.4 | -27%* | 48.5 | 35.4 |

<sub>\* presigned = 2 ops total; high noise.</sub>

Compatibility gate (RustFS): **all PASS**, and notably `multipart_listing` reports
`dir_prefix_match=True` — RustFS fixes the MinIO #7632 directory-prefix limitation.

## Issues & quirks log

- **[MinIO] multipart-upload listing ignores directory prefixes.** Reproduced against the
  baseline: `list_multipart_uploads(Prefix="some/dir/")` returns nothing for an in-flight
  upload, while a full-key prefix matches. This is
  [minio/minio#7632](https://github.com/minio/minio/issues/7632). Platform code
  (`list_ongoing_multipart_uploads`) calls it **without** a prefix (works), so this is
  informational — but it confirms the harness correctly detects vendor divergences. The
  compat check treats no-prefix listing as the hard requirement and reports prefix semantics
  informationally. RustFS matches both (verified `dir_prefix_match=True`), i.e. strictly
  more AWS-correct than MinIO here.
- **[harness] aioboto3 streaming.** `get_object()["Body"]` must be read directly
  (`await body.read(n)`), not wrapped in `async with` (which yields an aiohttp `ClientResponse`
  whose `read()` takes no size argument). Now matches `aws_library`.
- **[RustFS] `list_objects_v2` pagination is ~7x slower than MinIO** (1252 vs 9218 keys/s
  over 2000 flat keys; reproduced in a second run). Likely pagination implementation cost
  on the rc release. Relevant for large folder listings in the file picker; re-measure at
  1.0 GA.
- **[RustFS] server-side copy is ~2x slower** (488 vs 973 MB/s for a 64 MiB multipart copy).
- **[verified] RustFS runtime facts** (upstream README/Dockerfile/compose at `1.0.0-rc.6`):
  env `RUSTFS_ACCESS_KEY`/`RUSTFS_SECRET_KEY`; health `GET :9000/health` returns
  `{"status":"ok"}` (verified live); console on container port 9001 gated by
  `RUSTFS_CONSOLE_ENABLE`; image runs as UID/GID 10001 and bakes `/data` ownership, so a
  **named** volume inherits correct permissions (bind mounts need `chown 10001:10001`).
- **[repo] `.env` files are gitignored** — only `.env-devel` variants are tracked; local
  copies updated separately.
- **[pydantic] `R_CLONE_PROVIDER=MINIO` now fails fast** with a validation error — intended
  migration signal; external `.env` copies (`osparc-ops`) must be updated by their owners.
- **[left-behind naming]** `servicelib.minio_utils` (a generic retry-policy helper, nothing
  MinIO-specific) and historical comments about MinIO error-body quirks were intentionally
  left untouched — renaming them touches many unrelated imports (out of scope).
- **[lint debt]** Commits that touched test files surfaced pre-existing ruff violations in
  those files (E501/SLF001/ASYNC240/PT011 — ruff only lints staged files); fixed minimally
  (line splits, targeted `noqa`) in the same commits.

## Validation performed

- `packages/settings-library` `test_utils_r_clone.py`: **7 passed** (provider enum/mapping).
- `services/director-v2` `tests/unit/test_core_settings.py`: **43 passed**.
- Both ops compose files render via `docker compose config` (exit 0).
- `tests/environment-setup`: 167 passed; the only 2 real failures
  (`test_there_are_no_docker_compose_v1_anywhere`,
  `test_all_images_have_the_same_python_version`) reproduce identically on the pristine base
  commit — pre-existing and unrelated.
- Live RustFS container (`rustfs/rustfs:1.0.0-rc.6@sha256:8d8bfa61…`, host port 9001): full
  benchmark + compat gate **all green**, including the versioning/undelete flow, presigned
  part uploads, and `ChecksumMode=ENABLED`.

## Migration notes for deployers

- `R_CLONE_PROVIDER=MINIO` / `AGENT_VOLUMES_CLEANUP_S3_PROVIDER=MINIO` will be **rejected** by
  pydantic after this change — set them to `RUSTFS`.
- The external `osparc-ops` deployment `.env` must be updated accordingly (out of scope here;
  ops team to be notified).
- Bucket versioning remains provisioned by the deployment; unchanged.
- The old dev volume `ops_minio_data` is orphaned by the rename (new: `ops_s3_storage_data`).
  Remove it once its contents are confirmed disposable, or migrate data via S3 (rclone) first.
- Web console port changed: MinIO console was `9090:9090`; RustFS console is `9090:9001`
  (ops stack; disabled in the CI stack). S3 API host port `9001` unchanged.

## Summary of changes

Branch `enhancement/s3-rustfs-replacement` (8 commits on top of master `040e002fa`):

| commit | content |
|---|---|
| `388f32df5` | S3 benchmark/compatibility harness + MinIO baseline (`scripts/s3-benchmark/`) |
| `3b3b49fc4` | This report seeded with discovery findings + MinIO baseline |
| `8f5e4e740` | `S3Provider.RUSTFS` (rclone `Other`), `MINIO` removed (`settings-library` + test) |
| `c8ffe535a` | `.env-devel` provider values `MINIO` -> `RUSTFS` |
| `76d4a91b1` | ~25 files: provider refs `MINIO` -> `RUSTFS` (director-v2, dynamic-sidecar, agent, simcore-sdk, migrate_project docs, webserver third-party list) |
| `dde327bd6` | compose swap: service `minio` -> `s3-storage` = `rustfs/rustfs:1.0.0-rc.6` (digest-pinned), `/health` healthcheck, volume `ops_s3_storage_data`, Makefile banner |
| `fb68ff9a9` | pytest harness rename `minio_service.py` -> `s3_storage_service.py`, fixtures, selections, plugin strings |
| (final) | RustFS benchmark results (`scripts/s3-benchmark/results-rustfs.json`) + this report finalized |

Application S3 code (`aws_library.s3`) is **untouched** — the swap is transparent through
the aioboto3/SigV4 abstraction, exactly as designed.

**Verdict:** RustFS `1.0.0-rc.6` passes every compatibility requirement (versioning
undelete, multipart listing incl. dir prefixes, error bodies, checksums, presigned parts)
at parity for the platform-dominant patterns (small-object put/get, streaming download,
multipart). Two perf regressions surfaced — `ListObjectsV2` pagination (~7x slower) and
server-side copy (~2x slower) — neither blocks the dev/CI swap, but both should be
re-checked at 1.0 GA. SeaweedFS remains the designated fallback if they matter in
production.
