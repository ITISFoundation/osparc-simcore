""" Basic configuration file

TODO create create_environment_file(.) to build a template env file with defaults
"""
# pylint: disable=C0111
# pylint: disable=cyclic-import

import logging
import os
import sys

import utils

_CDIR = os.path.dirname(sys.argv[0] if __name__ == '__main__' else __file__)


def default_client_dir():
    """ Location of qx ourdir when docker-compose is run in debug mode"""
    return os.path.normpath(os.path.join(_CDIR, "..", "..", "client", "source-output"))


def default_thrift_dirs():
    basedir = os.path.normpath(os.path.join(_CDIR, '..', 'services-rpc-api'))
    return utils.get_thrift_api_folders(basedir)


THRIFT_GEN_OUTDIR = os.environ.get(
    'THRIFT_GEN_OUTDIR') or default_thrift_dirs()


class CommonConfig:

    # Web service
    SIMCORE_WEB_HOSTNAME = os.environ.get('SIMCORE_WEB_HOSTNAME', '0.0.0.0')
    SIMCORE_WEB_PORT = os.environ.get('SIMCORE_WEB_PORT', 8080)
    SIMCORE_CLIENT_OUTDIR = os.environ.get(
        'SIMCORE_WEB_OUTDIR') or default_client_dir()

    # S4L computational service (rpc-thrift)
    CS_S4L_HOSTNAME = os.environ.get('CS_S4L_HOSTNAME', '172.16.9.89')
    CS_S4L_PORT_APP = os.environ.get('CS_S4L_PORT_APP', 9095)
    CS_S4L_PORT_MOD = os.environ.get('CS_S4L_PORT_MOD', 9096)

    THRIFT_GEN_OUTDIR = THRIFT_GEN_OUTDIR
    THRIFT_USE_MULTIPLEXED_SERVER = os.environ.get(
        'THRIFT_USE_MULTIPLEXED_SERVER', True)

    PUBLIC_S3_URL = os.environ.get('PUBLIC_S3_URL', 'play.minio.io:9000')
    PUBLIC_S3_ACCESS_KEY = os.environ.get('PUBLIC_S3_ACCESS_KEY', 'Q3AM3UQ867SPQQA43P2F')
    PUBLIC_S3_SECRET_KEY = os.environ.get('PUBLIC_S3_SECRET_KEY', 'zuf+tfteSlswRu7BJ86wekitnifILbZam1KYY3TG')

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(CommonConfig):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG


class TestingConfig(CommonConfig):
    LOG_LEVEL = logging.DEBUG
    TESTING = True


class ProductionConfig(CommonConfig):
    LOG_LEVEL = logging.WARNING


CONFIG = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,

    'default': DevelopmentConfig
}
