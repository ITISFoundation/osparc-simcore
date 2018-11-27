""" Application's command line .

Why does this file exist, and why not put this in __main__?

  You might be tempted to import things from __main__ later, but that will cause
  problems: the code will get executed twice:

  - When you run `python -msimcore_service_storage` python will execute
    ``__main__.py`` as a script. That means there won't be any
    ``simcore_service_storage.__main__`` in ``sys.modules``.
  - When you import __main__ it will get executed again (as a module) because
    there's no ``simcore_service_storage.__main__`` in ``sys.modules``.

"""
import argparse
import logging
import os
import sys

from .application import run_service
from .application_config import CLI_DEFAULT_CONFIGFILE, app_schema
from .cli_config import add_cli_options, config_from_options
from .utils import search_osparc_repo_dir
from typing import Dict

log = logging.getLogger(__name__)


def create_default_parser():
    return argparse.ArgumentParser(description='Service to manage data storage in simcore.')


def setup_parser(parser):
    """ Adds all options to a parser"""
    #parser.add_argument('names', metavar='NAME', nargs=argparse.ZERO_OR_MORE,
    #                help="A name of something.")

    add_cli_options(parser, CLI_DEFAULT_CONFIGFILE)

    # Add here more options ....

    return parser


def create_environ(*, skip_host_environ: bool=False) -> Dict[str, str]:
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
        environ.update({
            'OSPARC_SIMCORE_REPO_ROOTDIR': str(rootdir),
        })

    return environ



def parse(args, parser):
    """ Parse options and returns a configuration object """
    if args is None:
        args = sys.argv[1:]

    # ignore unknown options
    options, _ = parser.parse_known_args(args)

    config = config_from_options(options, app_schema, vars=create_environ())

    # TODO: check whether extra options can be added to the config?!
    return config


def main(args=None):
    parser = argparse.ArgumentParser(description='Service to manage data storage in simcore.')

    setup_parser(parser)
    config = parse(args, parser)

    # TODO: improve keys!
    log_level = config["main"]["log_level"]
    logging.basicConfig(level=getattr(logging, log_level))

    run_service(config)
