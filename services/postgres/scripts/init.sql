/*
Do not allow users to create new objects in the public schema

Must be executed against every created database (e.g. for simcore, for metabase, ...)
(as long as we use Postgres 14 or earlier)

Sources:
* https://wiki.postgresql.org/wiki/A_Guide_to_CVE-2018-1058:_Protect_Your_Search_Path
* https://www.reddit.com/r/PostgreSQL/comments/1hvxw0s/understanding_the_public_schema_in_postgresql/
*/

-- As a superuser, run the following command in all of your databases
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
