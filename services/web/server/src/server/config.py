"""
    Configurations magic
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

from .utils import get_thrift_api_folders

# paths
_CDIR = os.path.dirname(sys.argv[0] if __name__ == "__main__" else __file__)
SRC_DIR = pathlib.Path(__file__).parent.parent
CONFIG_DIR = SRC_DIR.parent / "config"

DEFAULT_CONFIG_PATH =  CONFIG_DIR / "server.yaml"
TEST_CONFIG_PATH = CONFIG_DIR / "server-test.yaml"

_LOGGER = logging.getLogger(__name__)

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
    return os.path.normpath(os.path.join(_CDIR, "..", "..", "..", "client", "source-output"))


def default_thrift_dirs():
    basedir = os.path.normpath(os.path.join(_CDIR, "..", "..", "services-rpc-api"))
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



def get_config(argv=None) -> dict:
    """
        Loads configuration based on the command line arguments
    """
    ap = argparse.ArgumentParser()

    # TODO: pass configuration to load via command line
    # TODO: pass configuration to init db via command line
    commandline.standard_argparse_options(
        ap,
        default_config=DEFAULT_CONFIG_PATH
    )

    # ignore unknown options
    options, _ = ap.parse_known_args(argv)

    config = commandline.config_from_options(options, T_SCHEMA)
    if "IS_CONTAINER_CONTEXT" in os.environ.keys():
        config["host"] = "0.0.0.0"
        config["postgres"]["host"] = "db"


    # extend
    if "test" in options.config:
        _LOGGER.debug("Loading testing configuration ...")
        config.update(vars(TestingConfig))
    else:
        _LOGGER.debug("Loading production configuration ...")
        config.update(vars(ProductionConfig))

    pprint.pprint(config)

    _LOGGER.debug("Loading config %s \n\t %s", argv, config)

    return config


# TODO: load different type of configurations i.e. development, test/ci , production, etc
