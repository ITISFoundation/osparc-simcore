-- select the projects with the services to update (replace the regexp accordingly. NOTE: % is equivalent to .* in SQL)
-- SELECT workbench
-- FROM projects
-- WHERE workbench::text SIMILAR TO '%-notebook", "version": "2.13.0"%'
-- replace the regexp in here in order to
UPDATE projects
SET workbench = (
    regexp_replace(
      workbench::text,
      '-notebook", "version": "2.13.0"',
      '-notebook", "version": "2.13.1"',
      'g'
    )::json
  )
WHERE workbench::text SIMILAR TO '%-notebook", "version": "2.13.0"%'
