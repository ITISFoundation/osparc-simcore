def get_metrics_namespace(application_name: str) -> str:
    return application_name.replace("-", "_")
