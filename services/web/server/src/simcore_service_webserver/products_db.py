import logging
from typing import Any, AsyncIterator, Optional, Pattern

import sqlalchemy as sa
from aiopg.sa.engine import Engine
from aiopg.sa.result import ResultProxy, RowProxy
from models_library.basic_regex import PUBLIC_VARIABLE_NAME_RE
from models_library.utils.change_case import snake_to_camel
from pydantic import BaseModel, Field, HttpUrl, validator
from simcore_postgres_database.models.products import jinja2_templates

from .db_base_repository import BaseRepository
from .db_models import products
from .statics_constants import FRONTEND_APPS_AVAILABLE

log = logging.getLogger(__name__)

#
# MODEL
#
class Product(BaseModel):
    """
    Pydantic model associated to db_models.Products table

    SEE descriptions in packages/postgres-database/src/simcore_postgres_database/models/products.py
    """

    name: str = Field(regex=PUBLIC_VARIABLE_NAME_RE)
    display_name: str
    host_regex: Pattern

    # EMAILS/PHONE
    support_email: str
    twilio_messaging_sid: Optional[str] = Field(
        default=None,
        min_length=34,
        max_length=34,
    )

    # MANUALS
    manual_url: HttpUrl
    manual_extra_url: Optional[HttpUrl] = None

    # ISSUE TRACKER
    issues_login_url: Optional[HttpUrl] = None
    issues_new_url: Optional[HttpUrl] = None
    feedback_form_url: Optional[HttpUrl] = None

    # TEMPLATES
    registration_email_template: Optional[str] = None  # template name

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

    def get_template_name_for(self, filename: str) -> Optional[str]:
        name = filename.removesuffix(".jinja2")
        if name in self.__fields__.keys():
            return getattr(self, name, None)
        return None


#
# REPOSITORY
#

_include_cols = [products.columns[f] for f in Product.__fields__]


async def iter_products(engine: Engine) -> AsyncIterator[RowProxy]:
    async with engine.acquire() as conn:
        async for row in conn.execute(sa.select(_include_cols)):
            assert row  # nosec
            yield row


class ProductRepository(BaseRepository):
    async def get_product(self, product_name: str) -> Optional[Product]:
        async with self.engine.acquire() as conn:
            result: ResultProxy = conn.execute(
                sa.select(_include_cols).where(products.c.name == product_name)
            )
            row: Optional[RowProxy] = await result.first()
            return Product.from_orm(row) if row else None

    async def get_template_content(
        self,
        template_name: str,
    ) -> str:
        async with self.engine.acquire() as conn:
            return await conn.scalar(
                sa.select([jinja2_templates.c.content]).where(
                    jinja2_templates.c.name == template_name
                )
            )

    async def get_product_template_content(
        self,
        product_name: str,
        product_template: sa.Column = products.c.registration_email_template,
    ) -> str:
        async with self.engine.acquire() as conn:
            oj = sa.join(
                products,
                jinja2_templates,
                product_template == jinja2_templates.c.name,
                isouter=True,
            )
            return await conn.scalar(
                sa.select([jinja2_templates.c.content])
                .select_from(oj)
                .where(products.c.name == product_name)
            )
