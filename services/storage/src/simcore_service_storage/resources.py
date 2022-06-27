""" Access to data resources installed with this package

"""
from servicelib.resources import ResourcesFacade

resources = ResourcesFacade(
    package_name=__name__,
    distribution_name="simcore-service-storage",
    config_folder="",
)
