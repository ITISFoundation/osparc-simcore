import pkg_resources

__version__: str = pkg_resources.get_distribution(
    "simcore-dask-task-models-library"
).version
