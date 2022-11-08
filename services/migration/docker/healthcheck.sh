#!/bin/sh

#
# The entrypoint script produces a file with path $SC_DONE_MARK_FILE
# to mark that the migration was successfully completed
#
exec test -f "${SC_DONE_MARK_FILE}"
