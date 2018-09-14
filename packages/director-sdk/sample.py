# install package like so:
# pip install -v  git+https://github.com/sanderegg/osparc-simcore.git@director-sdk#subdirectory=packages/director-sdk/python

import asyncio
import simcore_director_sdk

from simcore_director_sdk.rest import ApiException

configuration = simcore_director_sdk.Configuration()
configuration.host = configuration.host.format(host="localhost", port=8001, version="v1")
api_instance = simcore_director_sdk.UsersApi(simcore_director_sdk.ApiClient(configuration))

async def get_root():
    try:
        api_response = await api_instance.root_get()    
        print(api_response)
    except ApiException as e:
        print("Exception when calling UserApi->root_get: %s\n" % e)
async def get_services():
    try:
        api_response = await api_instance.services_get()
        print(api_response)
    except ApiException as e:
        print("Exception when calling UserApi->root_get: %s\n" % e)

async def start_service():
    try:
        api_response = await api_instance.running_interactive_services_post("simcore/services/dynamic/3d-viewer", "testing6")
        print(api_response)
    except ApiException as e:
        print("Exception when calling UserApi->root_get: %s\n" % e)

async def test_api():
    # await get_root()
    # await get_services()
    await start_service()
    print("do work")

loop = asyncio.get_event_loop()
loop.run_until_complete(test_api())