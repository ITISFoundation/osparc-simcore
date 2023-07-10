""" Access to data resources installed with this package

"""
from servicelib.resources import DataResourcesFacade

storage_resources = DataResourcesFacade(
    package_name=__name__,
    distribution_name="simcore-service-storage",
)


__all__: tuple[str, ...] = ("storage_resources",)
