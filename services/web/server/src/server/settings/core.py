import argparse
import logging
import functools

from .schema import OPTIONS_SCHEMA

import trafaret_config as _tc
import trafaret_config.commandline as _tc_cli

_LOGGER = logging.getLogger(__name__)

def dict_from_class(cls) -> dict:
    return dict( (key, getattr(cls, key)) for key in dir(cls)  if not key.startswith("_")  )


def add_cli_options(ap=None):
    """
        Adds settings group to cli with options::

        -c CONFIG, --config CONFIG
                                Configuration file (default: 'config.yaml')
        --print-config        Print config as it is read after parsing and exit
        --print-config-vars   Print variables used in configuration file
        -C, --check-config    Check configuration and exit
    """
    if ap is None:
        ap = argparse.ArgumentParser()

    _tc.commandline.standard_argparse_options(
        ap.add_argument_group('settings'),
        default_config='config.yaml')
    return ap


config_from_options = functools.partial(_tc_cli.config_from_options, trafaret=OPTIONS_SCHEMA)

def config_from_file(filepath) -> dict:
    """
        Loads and validates app configuration from file
        Some values in the configuration are defined as environment variables

        Raises trafaret_config.ConfigError
    """
    config = _tc.read_and_validate(filepath, OPTIONS_SCHEMA)
    return config
