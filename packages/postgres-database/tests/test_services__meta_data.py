# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import random
from typing import NamedTuple

import pytest
import sqlalchemy as sa
from faker import Faker
from packaging.version import Version
from pytest_simcore.helpers.rawdata_fakers import random_group
from simcore_postgres_database.models.groups import GroupType, groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_latest,
    services_meta_data,
)
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert


class ServicesFixture(NamedTuple):
    expected_latest: dict
    num_services: int
    expected_public_service: dict


@pytest.fixture
def services_fixture(faker: Faker, pg_sa_engine: sa.engine.Engine) -> ServicesFixture:
    # fake metadata from image
    # emulate background
    #  - inject to database
    #  - create permissions

    expected_latest = {}

    with pg_sa_engine.connect() as conn:
        # need PRODUCT
        product_name = conn.execute(
            products.insert()
            .values(
                name="osparc",
                display_name="Product Osparc",
                short_name="osparc",
                host_regex=r"^osparc.",
                priority=0,
            )
            .returning(products.c.name)
        ).scalar()

        # need GROUPS
        product_gid = conn.execute(
            groups.insert()
            .values(**random_group(type=GroupType.STANDARD, name="osparc group"))
            .returning(groups.c.gid)
        ).scalar()
        everyone_gid = conn.execute(
            sa.select(groups.c.gid).where(groups.c.type == GroupType.EVERYONE)
        ).scalar()

        assert product_gid != everyone_gid

        # fill w/ different versions
        num_services = 3
        expected_public_service = {}

        for service_index in range(num_services):
            service_name = faker.name()
            key = f"simcore/services/dynamic/{service_name.lower().replace(' ','')}"

            expected_latest[key] = "0.0.0"

            num_versions = 4
            for _ in range(num_versions):
                version = faker.numerify("%#.%#.%##")
                if Version(expected_latest[key]) < Version(version):
                    expected_latest[key] = version

                query = services_meta_data.insert().values(
                    key=key,
                    version=version,
                    name=service_name,
                    description=faker.sentence(),
                    thumbnail=faker.image_url(120, 120),
                    classifiers=faker.random_choices(elements=("osparc", "nih", "foo"))
                    if service_index % 2
                    else [],
                )
                conn.execute(query)

                # services_access_rights = everyone
                query = services_access_rights.insert().values(
                    key=key,
                    version=version,
                    gid=everyone_gid,
                    execute_access=True,
                    write_access=False,
                    product_name=product_name,
                )

                # services_consume_filetypes
                num_filetypes = random.randint(0, 4)
                for i, filetype in enumerate(
                    faker.uri_extension().removeprefix(".")
                    for _ in range(num_filetypes)
                ):
                    is_public = random.choice([True, False])
                    query = services_consume_filetypes.insert().values(
                        service_key=key,
                        service_version=version,
                        service_display_name=service_name,
                        service_input_port=f"input_{i}",
                        filetype=filetype.upper(),
                        is_guest_allowed=is_public,
                    )

                    if is_public:
                        expected_public_service = {"key": key, "version": version}

                conn.execute(query)
    return ServicesFixture(
        expected_latest=expected_latest,
        num_services=num_services,
        expected_public_service=expected_public_service,
    )


def test_it1():

    Base = sa.orm.declarative_base()
    metadata = Base.metadata

    company_id = 1

    t_folders = sa.Table(
        "t_folders",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("company_id", sa.Integer),
    )

    t_milestones = sa.Table(
        "t_milestones",
        metadata,
        sa.Column("folder_id", sa.Integer),
        sa.Column("is_done", sa.Boolean),
        sa.Column("value", sa.Float),
    )

    t_folders_members = sa.Table(
        "t_folders_members",
        metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("folder_id", sa.Integer),
        sa.Column("user_id", sa.Integer),
    )

    f = t_folders.c
    m = t_milestones.c
    members_t = t_folders_members

    f1 = (
        sa.select([f.id, sa.func.max(m.value).label("value")])
        .select_from(t_folders.join(t_milestones, f.id == m.folder_id))
        .where(
            sa.and_(
                f.company_id == company_id,
                m.is_done.is_(False),
            )
        )
        .group_by(f.id)
    ).alias("f1")

    f2 = sa.select([f1.c.id, f1.c.value, members_t.c.id]).select_from(
        f1.join(members_t, members_t.c.folder_id == f1.c.id)
    )

    print(f2)


@pytest.mark.testit
def test_it(services_fixture: ServicesFixture, pg_sa_engine: sa.engine.Engine):
    # lts = (
    #     sa.select(
    #         services_meta_data.c.key,
    #         sa.text(
    #             "array_to_string(MAX(string_to_array(version, '.')::int[]), '.') AS latest"
    #         ),
    #     ).group_by(services_meta_data.c.key)
    # ).alias("lts")

    # stmt = sa.select([lts.c.key, lts.c.latest, services_meta_data.c.name]).select_from(
    #     lts.join(
    #         services_meta_data,
    #         (services_meta_data.c.key == lts.c.key)
    #         & (services_meta_data.c.version == lts.c.latest),
    #     )
    # )

    from sqlalchemy.dialects.postgresql import ARRAY, INTEGER

    assert issubclass(INTEGER, sa.Integer)

    lts = (
        sa.select(
            services_meta_data.c.key,
            sa.func.array_to_string(
                sa.func.max(
                    sa.func.string_to_array(services_meta_data.c.version, ".").cast(
                        ARRAY(INTEGER)
                    )
                ),
                ".",
            ).label("latest"),
        ).group_by(services_meta_data.c.key)
    ).alias("lts")

    stmt = sa.select([lts.c.key, lts.c.latest, services_meta_data.c.name]).select_from(
        lts.join(
            services_meta_data,
            (services_meta_data.c.key == lts.c.key)
            & (services_meta_data.c.version == lts.c.latest),
        )
    )
    print(stmt)

    with pg_sa_engine.connect() as conn:

        # rows: list = conn.execute(services_latest).fetchall()
        rows: list = conn.execute(stmt).fetchall()
        print(rows)


def test_trial_queries_for_service_metadata(
    services_fixture: ServicesFixture, pg_sa_engine: sa.engine.Engine
):
    # check if service exists and whether is public or not
    with pg_sa_engine.connect() as conn:
        query = sa.select(
            services_consume_filetypes.c.service_key,
            sa.func.array_agg(
                sa.func.distinct(services_consume_filetypes.c.filetype)
            ).label("file_extensions"),
        ).group_by(services_consume_filetypes.c.service_key)

        rows: list = conn.execute(query).fetchall()
        print(rows)

    with pg_sa_engine.connect() as conn:
        query = (
            sa.select(
                services_consume_filetypes.c.service_key,
                sa.text(
                    "array_to_string(MAX(string_to_array(version, '.')::int[]), '.') AS latest_version"
                ),
                sa.func.array_agg(
                    sa.func.distinct(services_consume_filetypes.c.filetype)
                ).label("file_extensions"),
            )
            .select_from(
                services_meta_data.join(
                    services_consume_filetypes,
                    services_meta_data.c.key
                    == services_consume_filetypes.c.service_key,
                )
            )
            .group_by(services_consume_filetypes.c.service_key)
        )

        rows: list = conn.execute(query).fetchall()

    with pg_sa_engine.connect() as conn:
        # Select query for latest
        latest_select_query = sa.select(
            services_meta_data.c.key,
            sa.text(
                "array_to_string(MAX(string_to_array(version, '.')::int[]), '.') AS version"
            ),
            # sa.func.max( sa.func.string_to_array(services_meta_data.c.version, ".").cast(sa.ARRAY(sa.Integer)).alias("latest_version") )
        ).group_by(services_meta_data.c.key)

        print(latest_select_query)
        rows: list = conn.execute(latest_select_query).fetchall()

        assert len(rows) == services_fixture.num_services
        assert set(services_fixture.expected_latest.items()) == set(rows)

        # Insert from select query (kept for reference)
        def _insert_latest():
            ins = services_latest.insert().from_select(
                [services_latest.c.key, services_latest.c.version], latest_select_query
            )
            print(ins)

            result = conn.execute(ins)  # fills services_latest the first time
            print(result)

        # Upsert from fetched value (alternative 1 - kept for reference)
        def _upsert_with_fetched_values():
            for row in rows:
                data = dict(row.items())
                upsert_query = (
                    pg_insert(services_latest)
                    .values(**data)
                    .on_conflict_do_update(
                        index_elements=[
                            services_latest.c.key,
                        ],
                        set_=dict(version=data["version"]),
                    )
                )

                conn.execute(upsert_query)

        # Upsert from subquery (alternative 2)
        query = pg_insert(services_latest).from_select(
            [services_latest.c.key, services_latest.c.version], latest_select_query
        )
        upsert_query = query.on_conflict_do_update(
            index_elements=[
                services_latest.c.key,
            ],
            set_=dict(version=query.excluded.version),
        )
        conn.execute(upsert_query)

        latest_values = conn.execute(services_latest.select()).fetchall()
        assert latest_values == rows

    # list latest services

    with pg_sa_engine.connect() as conn:
        query = sa.select(
            services_meta_data.c.key,
            services_meta_data.c.version,
            services_access_rights.c.gid,
            services_access_rights.c.execute_access,
            services_access_rights.c.write_access,
            services_access_rights.c.product_name,
        ).select_from(
            services_latest.join(
                services_meta_data,
                (services_meta_data.c.key == services_latest.c.key)
                & (services_meta_data.c.version == services_latest.c.version),
            ).join(
                services_access_rights,
                (services_meta_data.c.key == services_access_rights.c.key)
                & (services_meta_data.c.version == services_access_rights.c.version),
            )
        )
        print(query)

        query1 = query.where(services_meta_data.c.classifiers.contains(["osparc"]))

        query2 = query.where(
            sa.func.array_length(services_meta_data.c.classifiers, 1) > 0
        )

        # list services with gid=1 (x=1, w=0) and with type dynamic and classifier include osparc
        query3 = query.where(
            services_latest.c.key.like("simcore/services/dynamic/%%")
            & services_meta_data.c.classifiers.contains(["osparc"])
            & (services_access_rights.c.gid == 1)
            & (services_access_rights.c.execute_access == True)
        )

        for n, query in enumerate([query1, query2, query3]):
            print("query", n, "-----")
            rows = conn.execute(query).fetchall()
            assert len(rows) <= services_fixture.num_services
            print(rows)
