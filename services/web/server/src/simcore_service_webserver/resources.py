""" Access to data resources installed within this package

"""
from servicelib.resources import ResourcesFacade

resources = ResourcesFacade(
    package_name=__name__,
    distribution_name="simcore-service-webserver",
    config_folder='config',
)

__all__ = (
    'resources',
)
