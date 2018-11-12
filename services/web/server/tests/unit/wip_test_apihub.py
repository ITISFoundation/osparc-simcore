import attr
from yarl import URL


@attr.s(auto_attribs=True)
class ApiHubClient:
    origin = URL

import pytest


#@pytest
#def apihub(aiohttp_server):
#    pass

# load specs from file at simcore/api/specs/webserver/${version}/api

#def test_load_specs_from_hub(apihub):
#    client = ApiHubClient(origin=apihub)



# load specs from url at apihub:xxx/api/specs/webserver/${version}/api



# test oas servers
