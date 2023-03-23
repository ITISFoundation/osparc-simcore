# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
import sqlalchemy as sa
from faker import Faker
from simcore_postgres_database.models.services import (
    services_latest,
    services_meta_data,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert


@pytest.mark.testit
def test_it(faker: Faker, pg_sa_engine: sa.engine.Engine):
    with pg_sa_engine.connect() as conn:
        # fill w/ different versions
        for i in range(3):
            service_name = faker.name()

            for version in (
                f"{i}.0.0",
                "1.1.0",
                "1.1.10",
                "1.10.1",
                "2.1.0",
                "10.1.10",  # latest
            ):
                query = services_meta_data.insert().values(
                    key=f"simcore/services/dynamic/{service_name}",
                    version=version,
                    name=service_name,
                    description=faker.sentence(),
                    thumbnail=faker.image_url(120, 120),
                )

                conn.execute(query)

        subquery = sa.select(
            services_meta_data.c.key,
            sa.text(
                "array_to_string(MAX(string_to_array(version, '.')::int[]), '.') AS version"
            ),
            # sa.func.max( sa.func.string_to_array(services_meta_data.c.version, ".").cast(sa.ARRAY(sa.Integer)).alias("latest_version") )
        ).group_by(services_meta_data.c.key)

        print(subquery)
        print(".")

        ins = services_latest.insert().from_select(
            [services_latest.c.key, services_latest.c.version], subquery
        )
        print(ins)

        result = conn.execute(ins)  # fills services_latest the first time
        print(result)

        values = conn.execute(subquery).fetchall()

        for row in values:
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
        assert latest_values == values
