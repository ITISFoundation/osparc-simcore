SELECT * FROM "comp_tasks" WHERE node_id IN
  (SELECT node_id FROM "comp_tasks" GROUP BY node_id,project_id HAVING COUNT(*) > 1)
ORDER BY
  node_id


CREATE TABLE comp_tasks_temp;
INSERT INTO comp_tasks_temp
SELECT
  DISTINCT ON (project_id, node_id) *
FROM
  comp_tasks
ORDER BY
  project_id;

DROP TABLE comp_tasks;

ALTER TABLE comp_tasks_temp
RENAME TO comp_tasks;
