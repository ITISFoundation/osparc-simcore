from fastapi import FastAPI


async def backup_volume(app: FastAPI, volume_name: str) -> None:
    _ = app
    _ = volume_name
