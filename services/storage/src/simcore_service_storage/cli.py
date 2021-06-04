import logging
import os
import sys
from pprint import pformat

import click
from pydantic import ValidationError

from . import application
from .settings import create_settings_class

log = logging.getLogger(__name__)
HEADER = "{:-^50}"


@click.command("Service to manage data storage in simcore.")
@click.option(
    "--check-settings",
    "-C",
    default=False,
    is_flag=True,
    help="Validates settings, prints them and exits",
)
@click.option(
    "--show-settings-json-schema",
    default=False,
    is_flag=True,
    help="Checks building settings, prints result and exits",
)
def main(check_settings: bool = False, show_settings_json_schema: bool = False):

    json_schema: str = "Undefined"

    try:
        ApplicationSettings = create_settings_class()

        json_schema = ApplicationSettings.schema_json(indent=2)
        if show_settings_json_schema:
            click.echo(json_schema)
            sys.exit(os.EX_OK)

        settings = ApplicationSettings()

    except ValidationError as err:
        log.error(
            "Invalid application settings. Typically an environment variable is missing or mistyped :\n%s",
            "\n".join(
                [
                    HEADER.format("detail"),
                    str(err),
                    HEADER.format("environment variables"),
                    pformat(dict(os.environ)),
                    HEADER.format("json-schema"),
                    json_schema,
                ]
            ),
            exc_info=False,
        )
        sys.exit(os.EX_DATAERR)

    if check_settings:
        click.echo(settings.json(indent=2))
        sys.exit(os.EX_OK)

    log_level = settings.loglevel
    logging.basicConfig(level=getattr(logging, log_level))
    logging.root.setLevel(getattr(logging, log_level))

    application.run(settings)
