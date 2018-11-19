""" s3 subsystem's configuration

    - config-file schema
    - settings
"""
#import trafaret as T
from simcore_sdk.config.s3 import CONFIG_SCHEMA as _S3_SCHEMA

CONFIG_SECTION_NAME = 's3'

schema = _S3_SCHEMA
