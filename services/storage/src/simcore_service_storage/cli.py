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
import sys
import os

from . import application, cli_config
from servicelib.utils import search_osparc_repo_dir


log = logging.getLogger(__name__)


def create_environ(skip_system_environ=False):
    """
        Build environment of substitutable variables

    """
    # system's environment variables
    environ = {} if skip_system_environ else dict(os.environ)

    # project-related environment variables
    here = os.path.dirname(__file__)
    environ['THIS_PACKAGE_DIR'] = here

    rootdir = search_osparc_repo_dir(start=here)
    if rootdir is not None:
        environ['OSPARC_SIMCORE_REPO_ROOTDIR'] = str(rootdir)

    return environ



def setup(_parser):
    cli_config.add_cli_options(_parser)
    return _parser


def parse(args, _parser):
    """ Parse options and returns a configuration object """
    if args is None:
        args = sys.argv[1:]

    # ignore unknown options
    options, _ = _parser.parse_known_args(args)
    config = cli_config.config_from_options(options, vars=create_environ())

    # TODO: check whether extra options can be added to the config?!
    return config


parser = argparse.ArgumentParser(description='Service to manage data storage in simcore.')
setup(parser)


def main(args=None):
    config = parse(args, parser)

    log_level = config["main"]["log_level"]
    logging.basicConfig(level=getattr(logging, log_level))

    application.run(config)


# alias
setup_parser = setup
