#!/bin/sh
# FIXME: this uses too much CPU and is consuming all credit! Credit is based on CPU-time usage ( sum integral CPU%/time )
#
# how to check that upgrade completed?
#
SC_DONE_FILE=migration.done

exec test -f "${SC_DONE_FILE}"
