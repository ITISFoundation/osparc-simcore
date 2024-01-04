from ._resource_manager import ServicesManager


class ServicesTracker(ServicesManager):
    ...

    # TODO: hook into the tracking layer and add a task which actually
    # queries the services
    # TODO: this one pushes the messages over RPC to the frontend
