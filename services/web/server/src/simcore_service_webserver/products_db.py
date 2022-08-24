import logging
from typing import Any, Optional, Pattern

import sqlalchemy as sa
from aiohttp import web
from aiopg.sa.engine import Engine
from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, Field, HttpUrl, ValidationError, validator

from ._constants import APP_DB_ENGINE_KEY, APP_PRODUCTS_KEY
from .db_models import products
from .statics_constants import FRONTEND_APP_DEFAULT, FRONTEND_APPS_AVAILABLE

log = logging.getLogger(__name__)


class Product(BaseModel):
    """
    Pydantic model associated to db_models.Products table

    SEE descriptions in packages/postgres-database/src/simcore_postgres_database/models/products.py
    """

    name: str = Field(regex=PUBLIC_VARIABLE_NAME_RE)
    display_name: str
    host_regex: Pattern
    support_email: str
    twilio_messaging_sid: Optional[str] = Field(
        default=None,
        min_length=34,
        max_length=34,
    )
    manual_url: HttpUrl
    manual_extra_url: Optional[HttpUrl] = None
    issues_login_url: Optional[HttpUrl] = None
    issues_new_url: Optional[HttpUrl] = None
    feedback_form_url: Optional[HttpUrl] = None

    class Config:
        orm_mode = True

    @validator("name", pre=True, always=True)
    @classmethod
    def validate_name(cls, v):
        if v not in FRONTEND_APPS_AVAILABLE:
            raise ValueError(
                f"{v} is not in available front-end apps {FRONTEND_APPS_AVAILABLE}"
            )
        return v

    def to_statics(self) -> dict[str, Any]:
        """
        Selects **public** fields from product's info
        and prefixes it with its name to produce
        items for statics.json (reachable by front-end)
        """
        # SECURITY WARNING: do not expose sensitive information here
        public_selection = self.dict(
            include={
                "display_name",
                "support_email",
                "manual_url",
                "manual_extra_url",
                "issues_new_url",
                "issues_login_url",
                "feedback_form_url",
            },
            exclude_none=True,
        )
        # keys will be named as e.g. osparcDisplayName, osparcSupportEmail, osparcManualUrl, ...
        return {
            snake_to_camel(f"{self.name}_{key}"): value
            for key, value in public_selection.items()
        }


async def load_products_from_db(app: web.Application):
    """
    Loads info on products stored in the database into app's storage (i.e. memory)
    """
    app_products: dict[str, Product] = {}
    engine: Engine = app[APP_DB_ENGINE_KEY]
    exclude = {products.c.created, products.c.modified}

    async with engine.acquire() as conn:
        stmt = sa.select([c for c in products.columns if c not in exclude])
        async for row in conn.execute(stmt):
            assert row  # nosec
            try:
                name = row.name  # type:ignore
                app_products[name] = Product.from_orm(row)

                if name not in FRONTEND_APPS_AVAILABLE:
                    log.warning("There is not front-end registered for this product")

            except ValidationError as err:
                log.error(
                    "Invalid product in db '%s'. Skipping product info:\n %s", row, err
                )

    if FRONTEND_APP_DEFAULT not in app_products.keys():
        log.warning("Default front-end app is not in the products table")

    app[APP_PRODUCTS_KEY] = app_products
