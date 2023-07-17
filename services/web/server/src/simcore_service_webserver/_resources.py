""" Access to data resources installed within this package

"""
from servicelib.resources import DataResourcesFacade

webserver_resources = DataResourcesFacade(
    package_name=__name__,
    distribution_name="simcore-service-webserver",
)


__all__: tuple[str, ...] = ("webserver_resources",)
