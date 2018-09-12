# install package like so:
# pip install -v  pip install -v  git+https://github.com/ITISFoundation/osparc-simcore.git@webserver-sdk#subdirectory=packages/webserver-sdk/python
#
from contextlib import contextmanager
import asyncio
import simcore_webserver_sdk
import json

from simcore_webserver_sdk.rest import ApiException
from simcore_webserver_sdk.models.health_check_enveloped import HealthCheckEnveloped


@contextmanager
def api_client(cfg):
    client = simcore_webserver_sdk.ApiClient(cfg)
    try:
        yield client
    finally:
        #NOTE:  enforces to closing client session and connector.
        # this is a defect of the sdk
        del client.rest_client


async def run_test():
    cfg = simcore_webserver_sdk.Configuration()
    cfg.host = cfg.host.format(host="localhost", port=8080, version="v1")

    with api_client(cfg) as client:
        api = simcore_webserver_sdk.TestApi(client)
        res = await api.check_health()

        assert isinstance(res, HealthCheckEnveloped)
        assert res.status == 200
        print(res)
        res = await api.get_oas_doc()
        res = json.loads(res)
        assert res
        print(res)


loop = asyncio.get_event_loop()
loop.run_until_complete(run_test())
