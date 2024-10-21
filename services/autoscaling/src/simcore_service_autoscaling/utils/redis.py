import json

from fastapi import FastAPI

from ..core.settings import ApplicationSettings


def create_lock_key_and_value(app: FastAPI) -> tuple[str, str]:
    app_settings: ApplicationSettings = app.state.settings
    lock_key_parts = [app.title, app.version]
    lock_value = ""
    if app_settings.AUTOSCALING_NODES_MONITORING:
        lock_key_parts += [
            "dynamic",
            *app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
        ]
        lock_value = json.dumps(
            {
                "node_labels": app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
            }
        )
    elif app_settings.AUTOSCALING_DASK:
        lock_key_parts += [
            "computational",
            f"{app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL}",
        ]
        lock_value = json.dumps(
            {"scheduler_url": f"{app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL}"}
        )
    lock_key = ":".join(f"{k}" for k in lock_key_parts)
    return lock_key, lock_value
