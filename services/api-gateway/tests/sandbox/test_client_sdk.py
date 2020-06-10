# pylint: disable-all
# fmt: off

# simcore_api_sdk.abc.py
import abc as _abc
import json
from pprint import pprint
from typing import Any, Dict, List, Optional

import aiohttp

# DEV ---------------------------------------------------------------------
import attr
import pytest

# simcore_api_sdk/v0/me_api.py
from attr import NOTHING
from starlette.testclient import TestClient
from yarl import URL

from simcore_service_api_gateway import application, endpoints_check
from simcore_service_api_gateway.__version__ import api_vtag
from simcore_service_api_gateway.settings import AppSettings


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setenv("POSTGRES_USER", "test")
    monkeypatch.setenv("POSTGRES_PASSWORD", "test")
    monkeypatch.setenv("POSTGRES_DB", "test")
    monkeypatch.setenv("LOGLEVEL", "debug")
    monkeypatch.setenv("SC_BOOT_MODE", "production")

    # app
    test_settings = AppSettings()
    app = application.create(settings=test_settings)

    # routes
    app.include_router(endpoints_check.router, tags=["check"])

    # test client:
    # Context manager to trigger events: https://fastapi.tiangolo.com/advanced/testing-events/
    with TestClient(app) as cli:
        yield cli


@attr.s(auto_attribs=True)
class ApiResponse:
    status: int
    headers: Dict
    body: Dict


@attr.s(auto_attribs=True)
class ApiConfig:
    session: aiohttp.ClientSession
    api_key: str = attr.ib(repr=False)
    api_secret: str = attr.ib(repr=False)
    base_url: URL = URL(f"https://api.osparc.io/{api_vtag}/")

    # TODO: add validation here


class API(_abc.ABC):
    def __init__(self, cfg: ApiConfig, *, parent=None):
        self._cfg = cfg

    async def _make_request(
        self,
        method: str,
        url: str,
        *,
        url_params: Optional[Dict] = None,
        body_params: Optional[Dict] = None,
        headers: Optional[Dict] = None,
        body: bytes = b"",
        **requester_params: Any,
    ) -> ApiResponse:
        filled_url = self._cfg.base_url  # format_url(url, url_params)

        # TODO: it is always json !!
        if body_params is not None:
            body = json.dumps(body_params)

        resp: aiohttp.ClientResponse = await self._cfg.session.request(
            method, filled_url, body, headers, **requester_params
        )

        response = ApiResponse(
            status=resp.status, headers=resp.headers, body=await resp.json()
        )
        return response


# simcore_api_sdk/v0/__init__.py
# from ._openapi import ApiSession


class MeAPI(API):
    async def get(self):
        pass

    async def update(self, *, name: str = NOTHING, full_name: str = NOTHING):
        """
            Only writable fields can be updated
        """


@attr.s(auto_attribs=True)
class StudiesAPI(API):
    _next_page_token: int = NOTHING

    async def list(
        self,
        *,
        page_size: int = NOTHING,
        keep_page_token: bool = False,
        order_by: str = NOTHING,
        filter_fields: str = NOTHING,
    ):
        pass

    async def get(self, uid: str):
        pass

    async def create(self):
        pass

    async def update(self, uid: str, *, from_other=None, **study_fields):
        # TODO: how update fields like a.b.c.??
        pass

    async def remove(self, uid: str) -> None:
        # wait ??
        pass


# simcore_api_sdk/v0/_openapi.py
class ApiSession:
    def __init__(
        self, api_key: str, api_secret: str, base_url: URL = NOTHING,
    ):
        # TODO: setup auth here
        self.session = aiohttp.ClientSession(auth=None)

        cfg = ApiConfig(self.session, api_key, api_secret, base_url)
        self._cfg = cfg

        # API
        self.me = MeAPI(cfg)
        self.studies = StudiesAPI(cfg)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()


# ----------------------------------------------------
@pytest.mark.skip(reason="Under dev")
async def test_client_sdk():
    # TODO: design SDK for these calls
    # TODO: these examples should run test tests and automaticaly added to redoc

    # from simcore_api_sdk.v0 import ApiSession

    async with ApiSession(api_key="1234", api_secret="secret") as api:

        # GET /me is a special resource that is unique
        me: Profile = await api.me.get()
        pprint(me)

        # can update SOME entries
        await api.me.update(name="pcrespov", full_name="Pedro Crespo")

        # corresponds to the studies I have access ??

        ## https://cloud.google.com/apis/design/standard_methods

        # GET /studies
        studies: List[Dict] = await api.studies.list()

        # Implements Pagination: https://cloud.google.com/apis/design/design_patterns#list_pagination
        first_studies = await api.studies.list(page_size=3, keep_page_token=True)
        assert api.studies._next_page_token != NOTHING

        next_5_studies = await api.studies.list(page_size=5)

        # Results ordering: https://cloud.google.com/apis/design/design_patterns#sorting_order
        sorted_studies: List[Dict] = await api.studies.list(order_by="foo desc,bar")

        # List filter field: https://cloud.google.com/apis/design/naming_convention#list_filter_field
        studies: List[Dict] = await api.studies.list(filter_fields="foo.zoo, bar")
        assert studies[0]

        # GET /studies/{prj_id}
        prj: Dict = await api.studies.get("1234")

        # POST /studies
        new_prj: Study = await api.studies.create()

        # PUT or PATCH /studies/{prj_id}
        # this is a patch
        await api.studies.update(prj.id, description="Bar")

        # this is a put: using copy_from
        await api.studies.update(prj.id, copy_from=new_prj)

        # DELETE /studies/{prj_id}
        await api.studies.remove(prj.id)
