# Ops Request: S3 Bucket Lifecycle — Abort Incomplete Multipart Uploads

## Why this is needed

The storage service uses S3 multipart uploads for large files. If a client crashes
mid-upload, or a presigned upload is initiated but never completed, the partial
multipart upload remains on the bucket indefinitely, accumulating storage cost
and clutter. The application has its own cleanup loop (`dsm_cleaner`), but this
lifecycle rule is a **complementary defense-in-depth layer** enforced by the
storage backend itself — it guarantees that incomplete uploads cannot accumulate
even if the application cleanup is disabled, lagging, or buggy.

This rule does **not** delete completed objects and does **not** affect normal
read/write traffic. It only affects multipart uploads that have been initiated
but never completed.

## Scope

Apply to **every bucket used by the simcore storage service** (typically named
`simcore` and any per-environment variants).

---

## AWS S3

Apply once per bucket. Idempotent — re-running with the same configuration is a no-op.

```bash
BUCKET=simcore   # adjust per environment

aws s3api put-bucket-lifecycle-configuration \
    --bucket "$BUCKET" \
    --lifecycle-configuration '{
        "Rules": [
            {
                "ID": "abort-incomplete-multipart-uploads",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "AbortIncompleteMultipartUpload": {
                    "DaysAfterInitiation": 7
                }
            }
        ]
    }'
```

Verify:

```bash
aws s3api get-bucket-lifecycle-configuration --bucket "$BUCKET"
```

---

## Ceph (RadosGW S3)

Ceph RGW supports the standard S3 `PutBucketLifecycleConfiguration` API since
Luminous, so the **same `aws s3api` command above works against the RGW
endpoint** when pointed at it via `--endpoint-url` and the appropriate
credentials. Example:

```bash
BUCKET=simcore
RGW_ENDPOINT=https://rgw.example.org   # adjust

aws --endpoint-url "$RGW_ENDPOINT" s3api put-bucket-lifecycle-configuration \
    --bucket "$BUCKET" \
    --lifecycle-configuration '{
        "Rules": [
            {
                "ID": "abort-incomplete-multipart-uploads",
                "Status": "Enabled",
                "Filter": {"Prefix": ""},
                "AbortIncompleteMultipartUpload": {
                    "DaysAfterInitiation": 7
                }
            }
        ]
    }'
```

Notes for Ceph operators:
- Lifecycle processing on RGW runs on a schedule controlled by
  `rgw_lifecycle_work_time` / `rgw_lc_debug_interval`. Confirm the lifecycle
  worker is enabled on the cluster (default in modern releases).
- Verify with: `radosgw-admin lc list` and `radosgw-admin lc get --bucket=$BUCKET`.

---

## Parameters

| Setting | Value | Rationale |
|---|---|---|
| `DaysAfterInitiation` | `7` | Generous window for legitimate slow/resumed uploads, while preventing indefinite accumulation. The application-level cleanup uses 24h; this 7-day rule is the backstop. |
| `Filter.Prefix` | `""` (whole bucket) | Multipart uploads can occur under any project prefix. |
| `Status` | `Enabled` | Required for the rule to take effect. |

## Acceptance criteria

- `aws s3api get-bucket-lifecycle-configuration --bucket <bucket>` returns the rule above on every storage bucket in every environment.
- For Ceph: `radosgw-admin lc get --bucket=<bucket>` shows the rule.
