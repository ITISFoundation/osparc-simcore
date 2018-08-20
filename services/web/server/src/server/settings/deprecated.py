"""
    Configurations magic


    TODO: merge configs of all services used by the server here
"""
import os
import sys
import logging
import argparse
import pathlib
import pprint

# validates and transforms foreign data
import trafaret as T
from trafaret_config import commandline

from simcore_sdk.config.db import Config as DbConfig
# from simcore_sdk.config.s3 import Config as S3Config
# from simcore_sdk.config.docker import Config as S3Docker
# from simcore_sdk.config.rabbit import Config as S3Rabbit

from .utils import get_thrift_api_folders

_LOGGER = logging.getLogger(__name__)

# TODO: all paths should be handled with pathlib?
_CDIR = pathlib.Path(sys.argv[0] if __name__ == "__main__" else __file__).parent.parent
SRC_DIR = _CDIR.parent

# Config files
CONFIG_DIR = SRC_DIR.parent / "config"
DEFAULT_CONFIG_PATH =  CONFIG_DIR / "server.yaml"
TEST_CONFIG_PATH = CONFIG_DIR / "server-test.yaml"

T_SCHEMA = T.Dict({
    T.Key("postgres"):
    T.Dict({
        "database": T.String(),
        "user": T.String(),
        "password": T.String(),
        "host": T.String(),
        "port": T.Int(),
        "minsize": T.Int(),
        "maxsize": T.Int(),
    }),
    T.Key("host"): T.IP,
    T.Key("port"): T.Int(),
})


def default_client_dir():
    """ Location of qx ourdir when docker-compose is run in debug mode"""
    return os.path.normpath(os.path.join(str(_CDIR), "..", "..", "..", "client", "source-output"))


def default_thrift_dirs():
    basedir = os.path.normpath(os.path.join(str(_CDIR), "..", "..", "services-rpc-api"))
    return get_thrift_api_folders(basedir)


THRIFT_GEN_OUTDIR = os.environ.get(
    "THRIFT_GEN_OUTDIR") or default_thrift_dirs()


class CommonConfig:
    # Web service
    SIMCORE_WEB_HOSTNAME = os.environ.get("SIMCORE_WEB_HOSTNAME", "0.0.0.0")
    SIMCORE_WEB_PORT = os.environ.get("SIMCORE_WEB_PORT", 8080)
    SIMCORE_CLIENT_OUTDIR = os.environ.get(
        "SIMCORE_WEB_OUTDIR") or default_client_dir()

    # S4L computational service (rpc-thrift)
    CS_S4L_HOSTNAME = os.environ.get("CS_S4L_HOSTNAME", "172.16.9.89")
    CS_S4L_PORT_APP = os.environ.get("CS_S4L_PORT_APP", 9095)
    CS_S4L_PORT_MOD = os.environ.get("CS_S4L_PORT_MOD", 9096)

    THRIFT_GEN_OUTDIR = THRIFT_GEN_OUTDIR
    THRIFT_USE_MULTIPLEXED_SERVER = os.environ.get(
        "THRIFT_USE_MULTIPLEXED_SERVER", True)

    PUBLIC_S3_URL = os.environ.get("PUBLIC_S3_URL", "play.minio.io:9000")
    PUBLIC_S3_ACCESS_KEY = os.environ.get("PUBLIC_S3_ACCESS_KEY", "Q3AM3UQ867SPQQA43P2F")
    PUBLIC_S3_SECRET_KEY = os.environ.get("PUBLIC_S3_SECRET_KEY", "zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG")



class DevelopmentConfig(CommonConfig):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG


class TestingConfig(CommonConfig):
    LOG_LEVEL = logging.DEBUG
    TESTING = True


class ProductionConfig(CommonConfig):
    LOG_LEVEL = logging.WARNING


def dict_from_class(cls):
    return dict( (key, getattr(cls, key)) for key in dir(cls)  if not key.startswith("_")  )

def get_config(argv=None) -> dict:
    """
        Loads configuration based on the command line arguments
    """
    ap = argparse.ArgumentParser()

    # TODO: pass configuration to load via command line
    # TODO: pass configuration to init db via command line
    commandline.standard_argparse_options(
        ap,
        default_config=str(DEFAULT_CONFIG_PATH)
    )

    # ignore unknown options
    options, _ = ap.parse_known_args(argv)
    config = dict()

    # FIXME: merge properly all sources of options!
    config_from_envs = dict()
    if "test" in pathlib.Path(options.config).name:
        config_from_envs = dict_from_class(TestingConfig)
    else:
        config_from_envs = dict_from_class(ProductionConfig)

    config_from_file = commandline.config_from_options(options, T_SCHEMA)
    if "IS_CONTAINER_CONTEXT" in os.environ.keys():
        config_from_file["host"] = "0.0.0.0"
        config_from_file["postgres"]["host"] = "db"

    if "POSTGRES_ENDPOINT" in os.environ.keys():
        # config passed to simcore_sdk.config.db via environ in a docker
        #pylint: disable=W0212
        pg_config = DbConfig()
        config_from_file["postgres"]["database"] = pg_config._db
        config_from_file["postgres"]["user"] = pg_config._user
        config_from_file["postgres"]["password"] = pg_config._pwd
        _host, _port = pg_config._url.split(":")
        config_from_file["postgres"]["host"] = _host
        config_from_file["postgres"]["port"] = _port

    config.update( config_from_envs )
    config.update( config_from_file)

    logging.basicConfig(level=config["LOG_LEVEL"])
    _LOGGER.debug("Loading config %s \n\t %s", argv, pprint.pformat(config))

    return config


# TODO: load different type of configurations i.e. development, test/ci , production, etc
