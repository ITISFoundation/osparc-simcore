from simcore_service_webserver.db import is_service_enabled, is_service_responsive



async def test_responsive(server):
    app = server.app
    assert is_service_enabled(app)
    assert await is_service_responsive(app)
