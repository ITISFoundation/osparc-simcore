-- select group where to put users in
SELECT *
FROM "groups"
WHERE "name" LIKE '%GROUP_NAME%'
LIMIT 50 -- get the group id
  -- select the users which email ends like we are looking for
SELECT *
FROM "users"
WHERE (
    "email" LIKE '%@itis.swiss%'
    OR "email" LIKE '%@speag.swiss%'
    OR "email" LIKE '%@zmt.swiss%'
  )
