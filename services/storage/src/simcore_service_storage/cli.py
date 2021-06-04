import json
import logging
import os
import sys
from pathlib import Path
from pprint import pformat
from typing import Dict, List, Optional, Union

import click
import yaml
from pydantic import ValidationError

from . import application
from .resources import resources
from .settings import ApplicationSettings

log = logging.getLogger(__name__)


@click.command("Service to manage data storage in simcore.")
@click.option(
    "--check-settings",
    "-C",
    default=False,
    is_flag=True,
    help="Checks building settings, prints result and exits",
)
def main(check_settings: bool = False):
    try:
        settings = ApplicationSettings()

    except ValidationError as err:
        HEADER = "{:-^50}"
        log.error(
            "Invalid settings. %s:\n%s\n%s\n%s\n%s",
            err,
            HEADER.format("config_dict"),
            pformat(config_dict),
            HEADER.format("environment variables"),
            pformat(dict(os.environ)),
            exc_info=False,
        )
        sys.exit(os.EX_DATAERR)

    if check_settings:
        click.echo(settings.json(indent=2))
        sys.exit(os.EX_OK)

    log_level = settings.loglevel
    logging.basicConfig(level=getattr(logging, log_level))
    logging.root.setLevel(getattr(logging, log_level))

    # TODO: tmp converts all fields into primitive types
    cfg = json.loads(settings.json())
    application.run(config=cfg)
