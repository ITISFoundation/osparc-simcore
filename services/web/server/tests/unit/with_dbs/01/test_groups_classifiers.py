# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
import sqlalchemy as sa
from servicelib.common_aiopg_utils import DataSourceName, create_pg_engine
from simcore_service_webserver._constants import APP_AIOPG_ENGINE_KEY
from simcore_service_webserver.groups._classifiers_service import (
    GroupClassifierRepository,
)
from sqlalchemy.sql import text


@pytest.fixture
def inject_tables(postgres_db: sa.engine.Engine):
    stmt = text(
        """\
    INSERT INTO "group_classifiers" ("id", "bundle", "created", "modified", "gid", "uses_scicrunch") VALUES
    (2,	'{"vcs_ref": "asdfasdf", "vcs_url": "https://foo.classifiers.git", "build_date": "2021-01-20T15:19:30Z", "classifiers": {"project::dak": {"url": null, "logo": null, "aliases": [], "related": [], "markdown": "", "released": null, "classifier": "project::dak", "created_by": "Nicolas Chavannes", "github_url": null, "display_name": "DAK", "wikipedia_url": null, "short_description": null}, "organization::zmt": {"url": "https://zmt.swiss/", "logo": null, "aliases": ["Zurich MedTech AG"], "related": [], "markdown": "Zurich MedTech AG (ZMT) offers tools and best practices for targeted life sciences applications to simulate, analyze, and predict complex and dynamic biological processes and interactions. ZMT is a member of Zurich43", "released": null, "classifier": "organization::zmt", "created_by": "crespo", "github_url": null, "display_name": "ZMT", "wikipedia_url": null, "short_description": "ZMT is a member of Zurich43"}}, "collections": {"jupyterlab-math": {"items": ["crespo/osparc-demo"], "markdown": "Curated collection of repositories with examples of notebooks to run in jupyter-python-octave-math service", "created_by": "crespo", "display_name": "jupyterlab-math"}}}',	'2021-03-04 23:17:43.373258',	'2021-03-04 23:17:43.373258',	1,	'0');
    """
    )
    with postgres_db.connect() as conn:
        conn.execute(stmt)


@pytest.fixture
async def app(postgres_dsn: dict, inject_tables):
    dsn = DataSourceName(
        user=postgres_dsn["user"],
        password=postgres_dsn["password"],
        database=postgres_dsn["database"],
        host=postgres_dsn["host"],
        port=postgres_dsn["port"],
    )

    async with create_pg_engine(dsn) as engine:
        fake_app = {APP_AIOPG_ENGINE_KEY: engine}
        yield fake_app


async def test_classfiers_from_bundle(app):
    repo = GroupClassifierRepository(app)

    assert not await repo.group_uses_scicrunch(gid=1)

    bundle = await repo.get_classifiers_from_bundle(gid=1)
    assert bundle

    # Prunes extras and excludes unset and nones
    assert bundle["classifiers"]["project::dak"] == {
        "classifier": "project::dak",
        "display_name": "DAK",
    }
