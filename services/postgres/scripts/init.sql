/*
Do not allow users to create new objects in the public schema

Must be executed against every created database (e.g. for simcore, for metabase, ...)
(from Postgres 15 onwards the default ACL already excludes PUBLIC from CREATE on the
public schema; keeping this statement is an idempotent safeguard e.g. after manual grants)

Sources:
* https://wiki.postgresql.org/wiki/A_Guide_to_CVE-2018-1058:_Protect_Your_Search_Path
* https://www.reddit.com/r/PostgreSQL/comments/1hvxw0s/understanding_the_public_schema_in_postgresql/
*/

-- As a superuser, run the following command in all of your databases
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
