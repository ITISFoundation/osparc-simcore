# Maintenance scripts

Standalone `uv` scripts for operating on a running osparc-simcore deployment. Each script
declares its own dependencies inline (PEP 723) and can be run directly, `uv` takes care of
creating an ephemeral environment on the fly:

```bash
./clean_projects_of_user.py --help
# or
uv run clean_projects_of_user.py --help
```

## Scripts

- `clean_projects_of_user.py`: deletes all (or one) projects owned by a user on a given endpoint.
- `create_user.py`: registers a new user on a given endpoint.
- `image_triage.py`: lists image tags in a docker registry, split into computational/dynamic services.
- `import_projects_as_template.py`: imports a project file and publishes it as a template.
- `pre_registration.py`: pre-registers users from a JSON file and manages invitations.
- `zombies_cleaner.py`: inspects/cleans up orphaned computational pipelines and S3 objects (requires `simcore-postgres-database`/`simcore-common-library`, see script header for details).

## Subfolders

`autoscaled-monitor/` and `migrate_project/` are separate tools with their own dependency
management (see their respective `README.md`).
