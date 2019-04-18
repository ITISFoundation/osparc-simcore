#!/usr/bin/python

""" Tries to pull the node data from S3. Will return error code unless the --silent flag is on and only a warning will be output.

    Usage python state_puller.py PATH_OR_FILE --silent
:return: error code
"""

import argparse
import asyncio
import logging
import sys
from enum import IntEnum
from pathlib import Path

from simcore_sdk.node_data import data_manager
from simcore_sdk.node_ports import exceptions

log = logging.getLogger(__file__ if __name__ == "__main__" else __name__)
logging.basicConfig(level=logging.INFO)

class ExitCode(IntEnum):
    SUCCESS = 0
    FAIL = 1

def main(args = None) -> int:
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("path", help="The folder or file to get for the node", type=Path)
        parser.add_argument("--silent", help="The script will silently fail if the flag is on", default=False, const=True, action="store_const", required=False)
        options = parser.parse_args(args)

        loop = asyncio.get_event_loop()
        loop.run_until_complete(data_manager.pull(options.path))
        return ExitCode.SUCCESS

    except exceptions.S3InvalidPathError:
        if options.silent:
            log.warning("Could not retrieve state from S3 for %s", options.path)
            return ExitCode.SUCCESS
        log.exception("Could not retrieve state from S3 for %s", options.path)
        return ExitCode.FAIL
    except: # pylint: disable=bare-except
        log.exception("Unexpected error when retrieving state from S3 for %s", options.path)
        return ExitCode.FAIL

if __name__ == "__main__":
    sys.exit(main())
