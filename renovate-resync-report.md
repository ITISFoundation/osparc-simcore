# Renovate lockfile resync: FAILED

The post-upgrade resync (`.github/renovate/resync_lockfiles.py`) could not
regenerate these lockfile directories for the pins `boto3==1.43.118 boto3-stubs==1.43.118 botocore==1.43.118 botocore-stubs==1.43.118 types-aiobotocore==3.10.0 types_aiobotocore_s3==3.10.0 types-boto3==1.43.118`:

- `packages/aws-library/requirements`
- `packages/simcore-sdk/requirements`
- `services/agent/requirements`
- `services/api-server/requirements`
- `services/dask-sidecar/requirements`
- `services/dynamic-sidecar/requirements`
- `services/resource-usage-tracker/requirements`
- `services/storage/requirements`
- `services/autoscaling/requirements`
- `services/clusters-keeper/requirements`

They are committed as the pip-compile manager produced them, so they may
still pin older, possibly vulnerable, versions of the updated packages.
Fix them before merging, e.g. by freeing the blocking pins and running
`make -C <directory> reqs upgrade="<package>==<version> ..."`, or by running
the resync script in a scratch `git worktree` and cherry-picking the result.
The uv resolution error of each directory is in the Renovate run log.
