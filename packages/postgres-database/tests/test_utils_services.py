# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from typing import Any, NamedTuple

import pytest
import sqlalchemy as sa
from faker import Faker
from pytest_simcore.helpers.rawdata_fakers import random_group
from simcore_postgres_database.models.groups import GroupType, groups
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_meta_data,
)
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from simcore_postgres_database.utils_services import create_select_latest_services_query
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.dialects.postgresql import insert as pg_insert


class RandomServiceFactory:
    def __init__(self, faker: Faker):
        self._faker = faker
        self._cache = {}  # meta

    def random_service_meta_data(self, **overrides) -> dict[str, Any]:
        #
        # NOTE: if overrides keys are wrong it will fail later as
        #      `sqlalchemy.exc.CompileError: Unconsumed column names: product_name`
        #
        name_suffix = self._faker.name().lower().replace(" ", "")
        version = self._faker.numerify("%#.%#.#")
        owner_gid = 1  # everybody

        row = dict(
            key=f"simcore/service/dynamic/{name_suffix}",
            version=version,
            owner=owner_gid,
            name=f"service {name_suffix}",
            description=self._faker.sentence(),
            thumbnail=self._faker.image_url(120, 120),
            classifiers=self._faker.random_elements(
                elements=("RRID:SCR_018997", "RRID:SCR_019001", "RRID:Addgene_44362"),
                unique=True,
            ),
            quality={},
        )
        row.update(overrides)

        self._cache = row

        return row

    def random_service_access_rights(self, **overrides) -> dict[str, Any]:
        default_value = self._get_service_meta_data()
        row = dict(
            key=default_value["key"],
            version=default_value["version"],
            gid=default_value["owner"],
            execute_access=True,
            write_access=True,
            product_name="osparc",
        )
        row.update(overrides)

        return row

    def random_service_consume_filetypes(
        self, port_index: int = 1, **overrides
    ) -> dict[str, Any]:
        default_value = self._get_service_meta_data()

        row = dict(
            service_key=default_value["key"],
            service_version=default_value["version"],
            service_display_name=default_value["name"],
            service_input_port=f"input_{port_index}",
            filetype=self._faker.uri_extension().removeprefix(".").upper(),
            is_guest_allowed=bool(port_index % 2),
        )

        row.update(overrides)
        return row

    def _get_service_meta_data(self):
        if not self._cache:
            raise ValueError("Run first random_service_meta_data(*)")
        return self._cache

    def reset(self):
        self._cache = {}


class ServiceInserted(NamedTuple):
    metadata: dict[str, Any]
    access: list[dict[str, Any]]
    filetypes: list[dict[str, Any]]


def execute_insert_service(
    conn,
    meta_data_values: dict[str, Any],
    access_rights_values: list[dict[str, Any]],
    filetypes_values: list[dict[str, Any]],
) -> ServiceInserted:
    query = services_meta_data.insert().values(**meta_data_values)
    conn.execute(query)

    for values in access_rights_values:
        query = services_access_rights.insert().values(**values)
        conn.execute(query)

    for values in filetypes_values:
        query = services_consume_filetypes.insert().values(**values)
        conn.execute(query)

    inserted = ServiceInserted(
        metadata=meta_data_values,
        access=access_rights_values,
        filetypes=filetypes_values,
    )
    print(inserted)
    return inserted


ServiceKeyStr = str
ServiceVersionStr = str


class ServicesFixture(NamedTuple):
    expected_latest: set[tuple[ServiceKeyStr, ServiceVersionStr]]
    num_services: int


@pytest.fixture
def services_fixture(faker: Faker, pg_sa_engine: sa.engine.Engine) -> ServicesFixture:
    expected_latest = set()
    num_services = 0

    with pg_sa_engine.begin() as conn:
        # PRODUCT
        osparc_product = dict(
            name="osparc",
            display_name="Product Osparc",
            short_name="osparc",
            host_regex=r"^osparc.",
            priority=0,
        )
        product_name = conn.execute(
            pg_insert(products)
            .values(**osparc_product)
            .on_conflict_do_update(
                index_elements=[products.c.name], set_=osparc_product
            )
            .returning(products.c.name)
        ).scalar()

        # GROUPS
        product_gid = conn.execute(
            groups.insert()
            .values(**random_group(type=GroupType.STANDARD, name="osparc group"))
            .returning(groups.c.gid)
        ).scalar()

        everyone_gid = conn.execute(
            sa.select(groups.c.gid).where(groups.c.type == GroupType.EVERYONE)
        ).scalar()

        assert product_gid != everyone_gid

        # SERVICE /one
        service_factory = RandomServiceFactory(faker=faker)
        service_latest = "10.2.33"
        for version in ("1.0.0", "10.1.0", service_latest, "10.2.2"):
            service = execute_insert_service(
                conn,
                service_factory.random_service_meta_data(
                    key="simcore/service/dynamic/one",
                    version=version,
                    owner=everyone_gid,
                ),
                [
                    service_factory.random_service_access_rights(
                        product_name=product_name
                    )
                ],
                [
                    service_factory.random_service_consume_filetypes(
                        port_index=1,
                    )
                ],
            )

            num_services += 1

            if version == service_latest:
                expected_latest.add(
                    (service.metadata["key"], service.metadata["version"])
                )

        # SERVICE /two
        service = execute_insert_service(
            conn,
            service_factory.random_service_meta_data(
                key="simcore/service/dynamic/two",
                version="1.2.3",
                owner=product_gid,
            ),
            [
                service_factory.random_service_access_rights(
                    product_name=product_name,
                    execute_access=True,
                    write_access=False,
                )
            ],
            [
                service_factory.random_service_consume_filetypes(port_index=1),
                service_factory.random_service_consume_filetypes(port_index=2),
            ],
        )
        num_services += 1
        expected_latest.add((service.metadata["key"], service.metadata["version"]))

    return ServicesFixture(
        expected_latest=expected_latest,
        num_services=num_services,
    )


def test_select_latest_services(
    services_fixture: ServicesFixture, pg_sa_engine: sa.engine.Engine
):
    assert issubclass(INTEGER, sa.Integer)

    lts = create_select_latest_services_query().alias("lts")

    stmt = sa.select(lts.c.key, lts.c.latest, services_meta_data.c.name).select_from(
        lts.join(
            services_meta_data,
            (services_meta_data.c.key == lts.c.key)
            & (services_meta_data.c.version == lts.c.latest),
        )
    )

    with pg_sa_engine.connect() as conn:
        latest_services: list = conn.execute(stmt).fetchall()
        assert {
            (s.key, s.latest) for s in latest_services
        } == services_fixture.expected_latest


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

    # list latest services
    services_latest = create_select_latest_services_query().alias("services_latest")

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
                & (services_meta_data.c.version == services_latest.c.latest),
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
