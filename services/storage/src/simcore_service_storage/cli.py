""" Application's command line .

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -m simcore_service_storage` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``simcore_service_storage.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``simcore_service_storage.__main__`` in ``sys.modules``.

"""
import sys
import logging
import os
from pathlib import Path
from pprint import pformat
from typing import Dict, List, Optional, Union
import json

import click
import yaml
from pydantic import ValidationError

from . import application
from .settings import ApplicationSettings

log = logging.getLogger(__name__)

JsonNode = Union[Dict, List]


def prune_config(cfg: JsonNode):
    """
    Converts
    {
        max_workers: 8
        monitoring_enabled: ${STORAGE_MONITORING_ENABLED}
        test_datcore:
            token_key: ${BF_API_KEY}
            token_secret: ${BF_API_SECRET}
    }
        -->

    {
        max_workers: 8
        test_datcore: {}
    }

    """
    if isinstance(cfg, Dict):
        for key in list(cfg.keys()):
            value = cfg[key]
            if isinstance(value, str) and value.startswith("${"):
                del cfg[key]
            elif isinstance(value, (List, Dict)):
                prune_config(cfg[key])

    elif isinstance(cfg, List):
        for item in cfg:
            prune_config(item)


@click.command("Service to manage data storage in simcore.")
@click.option(
    "--config",
    default=None,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False, writable=False, path_type=Path
    ),
)
@click.option(
    "--check-config",
    "-C",
    default=False,
    is_flag=True,
    help="Checks settings, prints and exit",
)
def main(config: Optional[Path] = None, check_config: bool = False):
    config_dict = {}

    try:
        if config:
            with open(config) as fh:
                config_dict = yaml.safe_load(fh)
            prune_config(config_dict)
            settings = ApplicationSettings(**config_dict)
        else:
            settings = ApplicationSettings.create_from_environ()
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

    if check_config:
        click.echo(settings.json(indent=2))
        sys.exit(os.EX_OK)

    log_level = settings.loglevel
    logging.basicConfig(level=getattr(logging, log_level))
    logging.root.setLevel(getattr(logging, log_level))

    # TODO: tmp converts all fields into primitive types
    cfg = json.loads(settings.json())
    application.run(config=cfg)
