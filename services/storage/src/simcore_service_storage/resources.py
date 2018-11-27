""" Access to data resources installed with this package

"""
from servicelib.resources import ResourcesFacade
from .settings import RSC_CONFIG_DIR_KEY # pylint: disable=unused-import

resources = ResourcesFacade(
    package_name=__name__,
    distribution_name="simcore-service-storage",
    config_folder=RSC_CONFIG_DIR_KEY,
)


__all__ = (
    'resources',
    'RSC_CONFIG_DIR_KEY'
)
