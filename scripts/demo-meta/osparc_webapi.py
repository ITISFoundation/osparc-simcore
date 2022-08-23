""" Simple client SDK for osparc web API (prototype concept)

"""
import getpass
import logging
import os
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generic, Iterator, Optional, Type, TypeVar
from uuid import UUID

import httpx
from httpx import HTTPStatusError
from pydantic import (
    AnyHttpUrl,
    AnyUrl,
    BaseModel,
    BaseSettings,
    EmailStr,
    Field,
    NonNegativeInt,
    SecretStr,
    ValidationError,
    conint,
)
from pydantic.generics import GenericModel

log = logging.getLogger(__name__)
logging.basicConfig(level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO")))


# MODELS --------------------------------

ItemT = TypeVar("ItemT")
DataT = TypeVar("DataT")


class Meta(BaseModel):
    limit: NonNegativeInt
    total: NonNegativeInt
    offset: NonNegativeInt
    count: NonNegativeInt


class PageLinks(BaseModel):
    self: AnyHttpUrl
    first: AnyHttpUrl
    prev: Optional[AnyHttpUrl]
    next: Optional[AnyHttpUrl]
    last: AnyHttpUrl


class Page(GenericModel, Generic[ItemT]):
    meta: Meta = Field(..., alias="_meta")
    data: list[ItemT]
    links: PageLinks = Field(..., alias="_links")


class Envelope(GenericModel, Generic[DataT]):
    data: Optional[DataT]
    error: Optional[Any]

    @classmethod
    def parse_data(cls, obj):
        return cls.parse_obj({"data": obj})


class CheckPoint(BaseModel):
    id: NonNegativeInt
    checksum: str
    tag: Optional[str] = None
    message: Optional[str] = None
    parent: Optional[NonNegativeInt] = None
    created_at: datetime


class ProjectRepo(BaseModel):
    project_uuid: UUID
    url: AnyUrl


class ParentMetaProjectRef(BaseModel):
    project_id: UUID
    ref_id: NonNegativeInt


class ProjectIteration(BaseModel):
    name: str
    parent: ParentMetaProjectRef
    iteration_index: NonNegativeInt
    workcopy_project_id: UUID


NodeIDStr = str
OutputIDStr = str
Outputs = dict[OutputIDStr, Any]


class ExtractedResults(BaseModel):
    progress: dict[NodeIDStr, conint(ge=0, le=100)] = Field(
        ..., description="Progress in each computational node"
    )
    labels: dict[NodeIDStr, str] = Field(
        ..., description="Maps captured node with a label"
    )
    values: dict[NodeIDStr, Outputs] = Field(
        ..., description="Captured outputs per node"
    )


class ProjectIterationResultItem(ProjectIteration):
    results: ExtractedResults


# API ----------------------------------------------


def ping(client: httpx.Client):
    r = client.get("/")
    return r


def login(client: httpx.Client, user: str, password: str):
    r = client.post(
        "/auth/login",
        json={
            "email": user,
            "password": password,
        },
    )
    try:
        r.raise_for_status()
    except HTTPStatusError as err:
        assert err.response.is_error  # nosec
        raise RuntimeError(err.response.json.get("error", err.response.text)) from err

    return r.json()


def get_profile(client: httpx.Client):
    r = client.get("/me")
    assert r.status_code == 200
    return r.json()["data"]


def iter_items(
    client: httpx.Client, url_path: str, item_cls: Type[ItemT]
) -> Iterator[ItemT]:
    """iterates items returned by a List std-method

    SEE https://google.aip.dev/132
    """

    def _relative_url_path(page_link: Optional[AnyHttpUrl]) -> Optional[str]:
        if page_link:
            return f"{page_link.path}".replace(client.base_url.path, "")
        return None

    next_url = url_path
    last_url = None

    while next_url and next_url != last_url:

        r = client.get(next_url)
        r.raise_for_status()

        page = Page[item_cls].parse_raw(r.text)
        for item in page.data:
            yield item

        next_url = _relative_url_path(page.links.next)
        last_url = _relative_url_path(page.links.last)


def iter_repos(client: httpx.Client) -> Iterator[ProjectRepo]:
    return iter_items(client, "/repos/projects", ProjectRepo)


def iter_checkpoints(client: httpx.Client, project_id: UUID) -> Iterator[CheckPoint]:
    return iter_items(
        client,
        f"/repos/projects/{project_id}/checkpoints",
        CheckPoint,
    )


def iter_project_iteration(
    client: httpx.Client, project_id: UUID, checkpoint_id: NonNegativeInt
):
    return iter_items(
        client,
        f"/projects/{project_id}/checkpoint/{checkpoint_id}/iterations",
        ProjectIteration,
    )


# SETUP ------------------------------------------
class ClientSettings(BaseSettings):

    OSPARC_API_URL: AnyUrl = Field(default="http://127.0.0.1.nip.io:9081/v0")
    OSPARC_USER_EMAIL: EmailStr
    OSPARC_USER_PASSWORD: SecretStr

    class Config:
        env_file = ".env-osparc-web.ignore"


def init():
    env_file = Path(ClientSettings.Config.env_file)
    log.info("Creating %s", f"{env_file}")
    kwargs = {}
    kwargs["OSPARC_API_URL"] = input("OSPARC_API_URL: ").strip() or None
    kwargs["OSPARC_USER_EMAIL"] = (
        input("OSPARC_USER_EMAIL: ") or getpass.getuser() + "@itis.swiss"
    )
    kwargs["OSPARC_USER_PASSWORD"] = getpass.getpass()
    with open(env_file, "wt") as fh:
        for key, value in kwargs.items():
            print(key, value)
            if value is not None:
                fh.write(f"{key}={value}\n")
    log.info("%s: %s", f"{env_file=}", f"{env_file.exists()=}")


def query_if_invalid_config():
    try:
        ClientSettings()
    except ValidationError:
        init()


@contextmanager
def setup_client() -> Iterator[httpx.Client]:
    settings = ClientSettings()

    client = httpx.Client(base_url=settings.OSPARC_API_URL)
    try:
        # check if online and login
        print(ping(client))

        # login
        login(
            client,
            user=settings.OSPARC_USER_EMAIL,
            password=settings.OSPARC_USER_PASSWORD.get_secret_value(),
        )
        # check is OK
        assert get_profile(client)

        yield client

    except Exception:  # pylint: global-except
        client.close()
        raise
