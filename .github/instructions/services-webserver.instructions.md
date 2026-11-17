---
applyTo: '**/services/web/server/**/*.py'
---

# Web-server instructions

## Related documents

- Read [DESIGN.md](../../services/web/server/docs/DESIGN.md) before designing
  endpoint structure, response models, or service composition. It defines the
  architecture, domain layers, and design invariants.
- Read [TESTS.md](../../services/web/server/docs/TESTS.md) before designing test
  fixtures or endpoint tests. It defines the testing invariants.

## Database access layering

- Database imports (`sqlalchemy`, `simcore_postgres_database`, and other
  DB-session details) belong only in the data-access layer
  (`_repository.py`, `db/` modules). The controller and service layers must not
  import them.
- The only database types a service layer may receive are `AsyncConnection` and
  `AsyncEngine`, passed in explicitly. Everything else about the database stays
  behind the repository.
