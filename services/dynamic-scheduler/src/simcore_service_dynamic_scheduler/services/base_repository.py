from typing import cast

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine


class BaseRepository:
    def __init__(self, engine: AsyncEngine):
        self.engine = engine


def get_repo[TRepo: BaseRepository](app: FastAPI, base_type: type[TRepo]) -> TRepo:
    assert isinstance(app.state.repositories, dict)  # nosec
    repo = app.state.repositories.get(base_type.__name__)
    assert isinstance(repo, base_type)  # nosec
    return cast(TRepo, repo)
