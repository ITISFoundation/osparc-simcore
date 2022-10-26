#!/bin/sh

# The entrypoint script should produce this file
# to mark the migration as successfully completed
SC_DONE_FILE=migration.done

exec test -f "${SC_DONE_FILE}"
