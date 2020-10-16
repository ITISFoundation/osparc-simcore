import uvicorn


def main():
    host_name = ".".join(["0" for _ in range(4)])  # codeclimate love
    uvicorn.run(
        "simcore_service_service_sidecar.app:app",
        host=host_name,
        port=8000,
        log_level="info",
    )
