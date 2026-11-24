# Environment variables management

As a developer you will need to extend the current env vars for a service.

The following rules must be followed:

1. for each service that requires it, add it to the
   `services/docker-compose.yml` file (such as `MY_VAR=${MY_VAR}`)
2. add a meaningful default value for development inside `.env-devel` so that
   developers can work, and that `osparc-simcore` is **self contained**.
3. inside the repo where devops keep all the secrets follow the instructions
   to add the new env var

## Local overrides

`make` generates `.env` by concatenating `.env-devel` and an optional,
git-ignored `.env.local`, appended last so its values win. Clone
`.env.local.example` to start one. Machine-specific values (a real internal
registry, say) belong there, not in `.env-devel` and not by editing `.env`,
which gets regenerated.

Override only keys that already exist in `.env-devel`. A variable introduced
solely in `.env.local` stays invisible to the tests that read `.env-devel`
directly, and they fail on it. The k8s equivalent is
`k8s/.env-devel-k8s-override`; deployment secrets belong to the repo in
rule 3.

## Breaking changes

- The S3 backend for development/CI changed from MinIO to RustFS (PR #9719).
  External `.env` files must set `R_CLONE_PROVIDER=RUSTFS` and
  `AGENT_VOLUMES_CLEANUP_S3_PROVIDER=RUSTFS`
  (the old `MINIO` values are rejected at settings parse time).
