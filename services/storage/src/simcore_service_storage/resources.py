""" Access to data resources installed with this package

"""
from simcore_servicelib.resources import Resources

from .settings import RESOURCE_KEY_OPENAPI

resources = Resources(__name__, config_folder='etc/simcore_service_storage')
