# Database Known Issues and Workarounds

---

```
IntegrityError) duplicate key value violates unique constraint   "projects_pkey"
DETAIL:  Key (id)=(5) already exists.

```
If ids are inserted in table (e.g. for testing), cloning COPIES the id and fails. See [this](https://stackoverflow.com/questions/40280158/postgres-sqlalchemy-auto-increment-not-working)


---
