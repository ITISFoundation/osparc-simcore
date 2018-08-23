""" Configuration file's schema

TODO: add more strict checks with re
"""
import argparse
import logging
import os

import trafaret_config as _tc
import trafaret_config.commandline as _tc_cli
import trafaret as T

from simcore_sdk.config import (
    db,
    rabbit,
    s3
)

__version__ = "1.0"

_LOGGER = logging.getLogger(__name__)

# TODO: import from director
_DIRECTOR_SCHEMA = T.Dict({
    "host": T.String(),
    "port": T.Int()
})

# TODO: import from ?? director as well??
_CS_S4L_SCHEMA = T.Dict({
    "host": T.String(),
    "app": T.Dict({
        "port": T.Int()
    }),
    "modeler": T.Dict({
        "port": T.Int()
    }),
})

_APP_SCHEMA = T.Dict({
    "host": T.IP,
    "port": T.Int(),
    "client_outdir": T.String(),
    "log_level": T.Enum("DEBUG", "WARNING", "INFO", "ERROR", "CRITICAL", "FATAL"),
    "testing": T.Bool()
})

# TODO: add support for versioning.
#   - check shema fits version
#   - parse/format version in schema
CONFIG_SCHEMA_V1 = T.Dict({
    "version": T.String(),
    T.Key("app"): _APP_SCHEMA,
    T.Key("director"): _DIRECTOR_SCHEMA,
    T.Key("postgres"): db.CONFIG_SCHEMA,
    T.Key("rabbit"): rabbit.CONFIG_SCHEMA,
    T.Key("s3"): s3.CONFIG_SCHEMA,
    T.Key("cs_s4l"): _CS_S4L_SCHEMA
})

CONFIG_SCHEMA = CONFIG_SCHEMA_V1

def dict_from_class(cls) -> dict:
    return dict( (key, getattr(cls, key)) for key in dir(cls)  if not key.startswith("_")  )


def add_cli_options(ap=None):
    """
        Adds settings group to cli with options:

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

#TODO: add a class as os._Environ that adds extra variables as ${workspaceFolder}
# currently defalts to vars=os.environ
# class Vars:
#     _vars = {"workspaceFolder": lazy_evaluate = "../../"}
#     def __getitem__(self, key):
#         if key in os.environ:
#             return os.environ[key]
#         else:
#             return self._vars[key]
#
# import os
# os.environ


def config_from_options(options, vars=None): # pylint: disable=W0622
    if vars is None:
        vars = os.environ
    return _tc_cli.config_from_options(options, trafaret=CONFIG_SCHEMA, vars=vars)

def read_and_validate(filename, vars=None): # pylint: disable=W0622
    if vars is None:
        vars = os.environ
    # NOTE: vars=os.environ in signature freezes default to os.environ before it gets
    return _tc.read_and_validate(filename, trafaret=CONFIG_SCHEMA, vars=vars)

#config_from_options = functools.partial(_tc_cli.config_from_options, trafaret=CONFIG_SCHEMA)
#read_and_validate = functools.partial(_tc.read_and_validate, trafaret=CONFIG_SCHEMA )

def config_from_file(filepath) -> dict:
    """
        Loads and validates app configuration from file
        Some values in the configuration are defined as environment variables

        Raises trafaret_config.ConfigError
    """
    config = _tc.read_and_validate(filepath, CONFIG_SCHEMA, vars=os.environ)
    return config



__all__ = (
    'CONFIG_SCHEMA',
    'add_cli_options',
    'config_from_options',
    'config_from_file'
)
