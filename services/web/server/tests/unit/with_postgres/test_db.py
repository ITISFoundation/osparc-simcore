from simcore_service_webserver.db import is_service_enabled, is_service_responsive

from sqlalchemy import sa


async def test_responsive(server):
    app = server.app
    assert is_service_enabled(app)
    assert await is_service_responsive(app)


from simcore_postgres_database.model.projects import projects, ProjectType

async def test_intensive_connections():
    i=0
    while i<1000:
        async with engine.acquire() as conn:
            query = projects.insert().values(
                type=ProjectType.STANDARD,
                uuid=f'idnumber{i}'
                name=f'name{i}',
                project_owner='me',
                workbench={}
            )
            await conn.execute(query)
            i+=1
            print(i)