# Database Models


## Rationale

- Every table in the database is maintained by a given service
- This maintainer service shall have all helpers associated to that table (e.g. extension functions over raw metadata model)

- Isolate package with all table schemas per database and service
- Models shall not be implemented inheriting from Base. Use instead [explicit table definitions](https://docs.sqlalchemy.org/en/latest/orm/mapping_styles.html#classical-mappings)
