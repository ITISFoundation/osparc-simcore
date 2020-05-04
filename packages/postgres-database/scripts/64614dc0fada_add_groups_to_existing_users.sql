CREATE OR REPLACE FUNCTION upgrade_user_table_with_groups() RETURNS VOID AS $$
DECLARE
    group_id BIGINT;
    temprow RECORD;
BEGIN
    FOR temprow IN SELECT id, name FROM "users" WHERE "primary_gid" IS NULL
    LOOP
        INSERT INTO "groups" ("name", "description") VALUES (temprow.name, 'primary group') RETURNING gid INTO group_id;
        INSERT INTO "user_to_groups" ("uid", "gid") VALUES (temprow.id, group_id);
        UPDATE "users" SET "primary_gid" = group_id WHERE "id" = temprow.id;
    END LOOP;
END; $$ LANGUAGE 'plpgsql';

SELECT upgrade_user_table_with_groups()
DROP FUNCTION upgrade_user_table_with_groups()