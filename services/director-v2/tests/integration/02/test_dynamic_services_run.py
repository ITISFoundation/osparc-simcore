"""
The test will start 3 dynamic services in the same project and check 
that the legacy and the 2 new dynamic-sidecar boot properly.

1. Creates a project containing the following services:
- httpbin
- httpbin-dynamic-sidecar
- httpbin-dynamic-sidecar-compose

2. Starts the projects
3. Checks for the status of the project simulating the frontend
4. When all services are up and running checks they reply correctly tot the API
"""
# TODO: implementation as mentioned above


async def test_legacy_and_dynamic_sidecar_run():
    assert True