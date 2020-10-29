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

import logging
import os
from pathlib import Path
from pprint import pformat

import click
import yaml
from pydantic import ValidationError

from . import application
from .settings import ApplicationSettings

log = logging.getLogger(__name__)


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
def main(config: Path, check_config: bool):
    config_dict = {}

    try:
        if config:
            with open(config) as fh:
                config_dict = yaml.safe_load(fh)
            settings = ApplicationSettings(**config_dict)
        else:
            settings = ApplicationSettings.create_from_environ()
    except ValidationError as err:
        log.error(
            "Invalid settings. %s: ----\n config_dict=%s \n environ: %s",
            err,
            pformat(config_dict),
            pformat(dict(os.environ)),
            exc_info=False,
        )
        exit(os.EX_DATAERR)

    if check_config:
        click.echo(settings.json(indent=2))
        exit(os.EX_OK)

    log_level = settings.loglevel
    logging.basicConfig(level=getattr(logging, log_level))
    logging.root.setLevel(getattr(logging, log_level))

    application.run(config=settings.dict())
