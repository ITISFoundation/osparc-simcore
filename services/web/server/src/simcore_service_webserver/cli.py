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
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import typer
from aiohttp import web
from models_library.basic_types import BuildTargetEnum
from settings_library.utils_cli import create_settings_command

from .application import create_application, run_service
from .application__schema import CLI_DEFAULT_CONFIGFILE, app_schema
from .application_settings import ApplicationSettings, convert_to_app_config
from .cli_config import add_cli_options, config_from_options
from .log import setup_logging
from .utils import search_osparc_repo_dir

# ptsvd cause issues with ProcessPoolExecutor
# SEE: https://github.com/microsoft/ptvsd/issues/1443
if os.environ.get("SC_BOOT_MODE") == "debug-ptvsd":
    import multiprocessing

    multiprocessing.set_start_method("spawn", True)

log = logging.getLogger(__name__)


def create_default_parser() -> ArgumentParser:
    return ArgumentParser(description="Service to manage data webserver in simcore.")


def setup_parser(parser: ArgumentParser) -> ArgumentParser:
    """Adds all options to a parser"""
    # parser.add_argument('names', metavar='NAME', nargs=argparse.ZERO_OR_MORE,
    #                help="A name of something.")

    add_cli_options(parser, CLI_DEFAULT_CONFIGFILE)

    # Add here more options ....

    return parser


def create_environ(*, skip_host_environ: bool = False) -> Dict[str, str]:
    """Build environment with substitutable variables


    :param skip_host_environ: excludes os.environ , defaults to False
    :param skip_host_environ: bool, optional
    :return: a dictionary of variables to replace in config file
    :rtype: Dict[str, str]
    """

    # system's environment variables
    environ = {} if skip_host_environ else dict(os.environ)

    # project-related environment variables
    rootdir = search_osparc_repo_dir()
    if rootdir is not None:
        environ.update(
            {
                "OSPARC_SIMCORE_REPO_ROOTDIR": f"{rootdir}",
            }
        )

    # DEFAULTS if not defined in environ
    # NOTE: unfortunately, trafaret does not allow defining default directly in the config.yamla
    # as docker-compose does: i.e. x = ${VARIABLE:default}.
    #
    # Instead, the variable has to be defined here ------------
    environ.setdefault("SMTP_USERNAME", "None")
    environ.setdefault("SMTP_PASSWORD", "None")
    environ.setdefault("SMTP_TLS_ENABLED", "0")
    environ.setdefault("WEBSERVER_LOGLEVEL", "WARNING")

    # ----------------------------------------------------------

    return environ


def parse(args: Optional[List], parser: ArgumentParser) -> Dict:
    """Parse options and returns a configuration object"""
    if args is None:
        args = sys.argv[1:]

    # ignore unknown options
    options, _ = parser.parse_known_args(args)
    config = config_from_options(options, app_schema, vars=create_environ())

    return config


def _setup_app(args: Optional[List] = None) -> Tuple[web.Application, Dict]:

    settings = ApplicationSettings.create_from_envs()
    if args:
        # parse & config file
        parser = ArgumentParser(
            description="Service to manage data webserver in simcore."
        )
        setup_parser(parser)
        config = parse(args, parser)
    else:
        config = convert_to_app_config(settings)

    setup_logging(
        level=settings.log_level,
        slow_duration=settings.AIODEBUG_SLOW_DURATION_SECS,
    )
    app = create_application(config)
    return (app, config)


async def app_factory() -> web.Application:
    # parse & config file
    app_settings = ApplicationSettings()
    assert app_settings.SC_BUILD_TARGET  # nosec
    log.info("Application settings: %s", f"{app_settings.json(indent=2)}")
    args = [
        "--config",
        "server-docker-dev.yaml"
        if app_settings.SC_BOOT_MODE == BuildTargetEnum.DEVELOPMENT
        else "server-docker-prod.yaml",
    ]
    app, _ = _setup_app(args)

    return app


# CLI -------------

main = typer.Typer(name="simcore-service-webserver")
main.command()(create_settings_command(settings_cls=ApplicationSettings, logger=log))


@main.command()
def run(
    config: Path = typer.Argument("config.yaml", help="Configuration file"),
    print_config: bool = False,
    print_config_vars: bool = False,
    check_config: bool = False,
):
    args = [
        "--config",
        str(config),
    ]

    if print_config:
        args.append(
            "--print-config",
        )

    if print_config_vars:
        args.append("--print-config-vars")

    if check_config:
        args.append("--check-config")

    app, cfg = _setup_app(args)
    run_service(app, cfg)
