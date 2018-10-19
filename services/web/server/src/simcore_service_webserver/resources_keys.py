""" Namespace to keep keys to identify resources


See resources module
"""
from .__version__ import get_version_object

package_version = get_version_object()


API_MAJOR_VERSION = package_version.major
API_URL_VERSION = "v{:.0f}".format(API_MAJOR_VERSION)

# RSC=resource
RSC_CONFIG_DIR_KEY = "config"
RSC_OPENAPI_DIR_KEY = "oas3/{}".format(API_URL_VERSION)
RSC_OPENAPI_ROOTFILE_KEY = "{}/openapi.yaml".format(RSC_OPENAPI_DIR_KEY)
RSC_CONFIG_DIR_KEY  = "config"

# RSC_CONFIG_SCHEMA_KEY = RSC_CONFIG_DIR_KEY + "/config-schema-v1.json"
