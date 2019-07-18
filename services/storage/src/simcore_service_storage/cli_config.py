
import argparse
import logging
import os

import trafaret_config
import trafaret_config.commandline as commandline

from .config_schema import schema
from .resources import RSC_CONFIG_DIR_KEY, resources
from .settings import DEFAULT_CONFIG

log = logging.getLogger(__name__)



def add_cli_options(argument_parser=None):
    """
        Adds settings group to cli with options:

        -c CONFIG, --config CONFIG
                                Configuration file (default: 'config.yaml')
        --print-config        Print config as it is read after parsing and exit
        --print-config-vars   Print variables used in configuration file
        -C, --check-config    Check configuration and exit
    """
    if argument_parser is None:
        argument_parser = argparse.ArgumentParser()

    commandline.standard_argparse_options(
        argument_parser.add_argument_group('settings'),
        default_config=DEFAULT_CONFIG)

    return argument_parser


def config_from_options(options, vars=None): # pylint: disable=W0622
    if vars is None:
        vars = os.environ

    if not os.path.exists(options.config):
        resource_name = options.config
        if resources.exists(resource_name):
            options.config = resources.get_path(resource_name)
        else:
            resource_name = RSC_CONFIG_DIR_KEY + '/' + resource_name
            if resources.exists(resource_name):
                options.config = resources.get_path(resource_name)

    log.debug("loading %s", options.config)

    return commandline.config_from_options(options, trafaret=schema, vars=vars)

def read_and_validate(filepath, vars=None): # pylint: disable=W0622
    if vars is None:
        vars = os.environ
    # NOTE: vars=os.environ in signature freezes default to os.environ before it gets
    # Cannot user functools.partial because os.environ gets then frozen
    return trafaret_config.read_and_validate(filepath, trafaret=schema, vars=vars)


def config_from_file(filepath) -> dict:
    """
        Loads and validates app configuration from file
        Some values in the configuration are defined as environment variables

        Raises trafaret_config.ConfigError
    """
    config = trafaret_config.read_and_validate(filepath, schema, vars=os.environ)
    return config
