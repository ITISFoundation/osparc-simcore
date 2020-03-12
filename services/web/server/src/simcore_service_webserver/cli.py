""" Application's command line .

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -msimcore_service_webserver` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``simcore_service_webserver.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``simcore_service_webserver.__main__`` in ``sys.modules``.

"""
import logging
import os
import sys
from argparse import ArgumentParser
from typing import Dict, List, Optional

from aiohttp.log import access_logger
from aiodebug import log_slow_callbacks

from .application import run_service
from .application_config import CLI_DEFAULT_CONFIGFILE, app_schema
from .cli_config import add_cli_options, config_from_options
from .utils import search_osparc_repo_dir

LOG_LEVEL_STEP = logging.CRITICAL - logging.ERROR

log = logging.getLogger(__name__)


def create_default_parser() -> ArgumentParser:
    return ArgumentParser(description="Service to manage data webserver in simcore.")


def setup_parser(parser: ArgumentParser) -> ArgumentParser:
    """ Adds all options to a parser"""
    # parser.add_argument('names', metavar='NAME', nargs=argparse.ZERO_OR_MORE,
    #                help="A name of something.")

    add_cli_options(parser, CLI_DEFAULT_CONFIGFILE)

    # Add here more options ....

    return parser


def create_environ(*, skip_host_environ: bool = False) -> Dict[str, str]:
    """ Build environment with substitutable variables


    :param skip_host_environ: excludes os.environ , defaults to False
    :param skip_host_environ: bool, optional
    :return: a dictionary of variables to replace in config file
    :rtype: Dict[str, str]
    """

    # system's environment variables
    environ = dict() if skip_host_environ else dict(os.environ)

    # project-related environment variables
    rootdir = search_osparc_repo_dir()
    if rootdir is not None:
        environ.update(
            {"OSPARC_SIMCORE_REPO_ROOTDIR": str(rootdir),}
        )

    # DEFAULTS if not defined in environ
    # NOTE: unfortunately, trafaret does not allow defining default directly in the config.yamla
    # as docker-compose does: i.e. x = ${VARIABLE:default}.
    #
    # Instead, the variable has to be defined here ------------
    environ.setdefault("WEBSERVER_DB_INITTABLES", "0")
    environ.setdefault("SMTP_USERNAME", "None")
    environ.setdefault("SMTP_PASSWORD", "None")
    environ.setdefault("SMTP_TLS_ENABLED", "0")
    environ.setdefault("WEBSERVER_LOGLEVEL", "WARNING")

    # ----------------------------------------------------------

    return environ


def parse(args: Optional[List], parser: ArgumentParser) -> Dict:
    """ Parse options and returns a configuration object """
    if args is None:
        args = sys.argv[1:]

    # ignore unknown options
    options, _ = parser.parse_known_args(args)
    config = config_from_options(options, app_schema, vars=create_environ())

    return config


def main(args: Optional[List] = None):
    # parse & config file
    parser = ArgumentParser(description="Service to manage data webserver in simcore.")
    setup_parser(parser)
    config = parse(args, parser)

    # service log level
    log_level = getattr(logging, config["main"]["log_level"])
    logging.basicConfig(level=log_level)
    logging.root.setLevel(log_level)
    # aiohttp access log-levels
    access_logger.setLevel(log_level)

    # keep mostly quiet noisy loggers
    quiet_level = max(min(log_level + LOG_LEVEL_STEP, logging.CRITICAL), logging.WARNING)
    logging.getLogger("engineio").setLevel(quiet_level)
    logging.getLogger("openapi_spec_validator").setLevel(quiet_level)
    logging.getLogger("sqlalchemy").setLevel(quiet_level)
    logging.getLogger("sqlalchemy.engine").setLevel(quiet_level)

    # NOTE: Every task blocking > AIODEBUG_SLOW_DURATION_SECS secs is considered slow and logged as warning
    slow_duration = float(os.environ.get("AIODEBUG_SLOW_DURATION_SECS", 0.1))
    log_slow_callbacks.enable(slow_duration)

    # run
    run_service(config)
