import uvicorn  # type: ignore


def main():
    uvicorn.run("scheduler.app:app", host="0.0.0.0", port=8000, log_level="info")
