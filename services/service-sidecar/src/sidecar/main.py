import uvicorn


def main():
    host_name = "0.0.0.0"
    uvicorn.run("sidecar.app:app", host=host_name, port=8000, log_level="info")
