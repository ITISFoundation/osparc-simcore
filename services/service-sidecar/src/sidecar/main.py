import uvicorn


def main():
    uvicorn.run("sidecar.app:app", host="0.0.0.0", port=8000, log_level="info")
