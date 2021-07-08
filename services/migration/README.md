# migration service

This service starts in the swarm, discovers postgres service and upgrades the database
to the latest version of of the schema.

While postgres service is not available, the process is continuously restarted.
Once a connection to postgress is the migration is applied. If the process succeeds
it will expose on port 8000 an http replying in plain text to `GET migration:8000/`.
