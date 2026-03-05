---
name: postgres-migration
description: Creates an Alembic migration script for PostgreSQL database schema changes. Use this skill when database models in `packages/postgres-database/src/simcore_postgres_database/models/` have changed (column additions, type changes, schema structure modifications, etc.).
---

## When to Use This Skill

Run this workflow whenever you make changes to the SQLAlchemy models in `packages/postgres-database/src/simcore_postgres_database/models/`. The resulting migration script ensures that production deployments can migrate all existing database data to the new schema.

During a development session, you may generate 2–3 smaller migration scripts (one per logical change) rather than one large script.

---

## Prerequisites

- Changes have been made to model files in `packages/postgres-database/src/simcore_postgres_database/models/`
- You are in the workspace root directory
- Docker is running (for the reference PostgreSQL database)

---

## Step 1: Check and Activate the Virtual Environment

From the workspace root, check if the `.venv` is already active:

```bash
which python
```

If it shows a path containing `.venv`, it is already active. Otherwise, activate it:

```bash
source .venv/bin/activate
```

---

## Step 2: Stop Any Existing PostgreSQL Database

Before setting up a fresh reference database, stop any running PostgreSQL container:

```bash
cd packages/postgres-database
make pg-down
```

---

## Step 3: Set Up the Reference Database

Navigate to the `packages/postgres-database` directory and initialize the reference database:

```bash
cd packages/postgres-database
make setup-commit
```

This command:
- Installs the `sc-pg` CLI tool
- Spins up a fresh PostgreSQL Docker container with the current schema
- Outputs logs with the Adminer URL (e.g., `http://127.0.0.1:18080/?pgsql=postgres&username=test&db=test&ns=public`)

Review the output logs to confirm the database is ready.

---

## Step 4: Generate the Migration Script

Run the `sc-pg review` command with a **short, descriptive message** of your schema changes. This message is used as part of the migration filename:

```bash
sc-pg review -m "add user_id column to projects table"
```

This command:
- Compares the current database state with your modified SQLAlchemy models
- Generates a new Alembic migration script in `packages/postgres-database/src/simcore_postgres_database/migration/`

Example output path:
```
packages/postgres-database/src/simcore_postgres_database/migration/versions/abc123def456_add_user_id_column_to_projects_table.py
```

---

## Step 5: Validate the Migration Script

**Inspect the generated migration file to verify it captures all your schema changes.**

Open the file and check:
- All new/modified columns are included
- Data types match your model changes
- Constraints (if any) are correct
- Relationship changes are reflected (if applicable)

**In rare cases**, the Alembic auto-generation may not capture complex changes. If you find missing or incorrect statements, manually edit the migration file to correct them.

---

## Step 6: Clean Up

Stop the reference PostgreSQL database:

```bash
make pg-down
```

---

## Scope

This skill **completes** with the generation and validation of the migration script. The responsibility for the following actions lies outside this skill:
- Committing the migration file to version control
- Running the migration in staging/production environments
- Testing the migration against production-like data
- Verifying backward compatibility

---

## Common Issues

| Issue | Solution |
|-------|----------|
| `sc-pg` command not found | Ensure `make setup-commit` ran successfully and the `.venv` is active |
| Migration file not generated | Check the logs from `sc-pg review` for errors; verify model changes were saved to disk |
| Migration missing some changes | Manually edit the migration file (Python code) to add missing operations (see Step 5) |
| Adminer URL not accessible | Check Docker logs with `docker logs <postgres_container_id>` or look at `make setup-commit` output |
