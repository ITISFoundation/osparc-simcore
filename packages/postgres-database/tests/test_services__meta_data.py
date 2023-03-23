# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
import sqlalchemy as sa
from faker import Faker
from packaging.version import Version
from simcore_postgres_database.models.services import (
    services_latest,
    services_meta_data,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert


@pytest.mark.testit
def test_it(faker: Faker, pg_sa_engine: sa.engine.Engine):
    expected_latest = {}

    with pg_sa_engine.connect() as conn:
        # fill w/ different versions
        num_services = 3

        for service_index in range(num_services):
            service_name = faker.name()
            key = f"simcore/services/dynamic/{service_name.lower().replace(' ','')}"

            expected_latest[key] = "0.0.0"

            num_versions = 4
            for _ in range(num_versions):
                version = faker.numerify("##.##.###")  # might hit same versioN!
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

    with pg_sa_engine.connect() as conn:
        # select query to find latest
        latest_select_query = sa.select(
            services_meta_data.c.key,
            sa.text(
                "array_to_string(MAX(string_to_array(version, '.')::int[]), '.') AS version"
            ),
            # sa.func.max( sa.func.string_to_array(services_meta_data.c.version, ".").cast(sa.ARRAY(sa.Integer)).alias("latest_version") )
        ).group_by(services_meta_data.c.key)

        print(latest_select_query)

        # Insert from select query
        def _insert_latest():
            ins = services_latest.insert().from_select(
                [services_latest.c.key, services_latest.c.version], latest_select_query
            )
            print(ins)

            result = conn.execute(ins)  # fills services_latest the first time
            print(result)

        rows: list = conn.execute(latest_select_query).fetchall()

        assert len(rows) == num_services
        assert set(expected_latest.items()) == set(rows)

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

            latest_values = conn.execute(services_latest.select()).fetchall()
            assert latest_values == rows

        # upsert from select of latest
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

    with pg_sa_engine.connect() as conn:
        # list latest services
        query = sa.select(services_meta_data).select_from(
            services_latest.join(
                services_meta_data,
                (services_meta_data.c.key == services_latest.c.key)
                & (services_meta_data.c.version == services_latest.c.version),
            )
        )
        query1 = query.where(services_meta_data.c.classifiers.contains(["osparc"]))
        query2 = query.where(
            sa.func.array_length(services_meta_data.c.classifiers, 1) > 0
        )

        print(query)

        for stmt in (query1, query2):
            rows = conn.execute(stmt).fetchall()
            assert len(rows) <= num_services
            print(rows)
