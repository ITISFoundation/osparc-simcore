# Environment variables management

To add an environment variable to a service:

1. Add it to `services/docker-compose.yml` for each service that needs it
   (e.g. `MY_VAR=${MY_VAR}`).
2. Add a development default in `.env-devel` so the repo works self-contained.
3. Follow the instructions in the devops secrets repo to add the variable there.

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
