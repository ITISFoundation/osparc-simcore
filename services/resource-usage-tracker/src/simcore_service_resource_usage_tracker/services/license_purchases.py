from typing import Annotated

from fastapi import Depends
from models_library.api_schemas_resource_usage_tracker.license_purchases import (
    LicensePurchaseGet,
    LicensesPurchasesPage,
)
from models_library.products import ProductName
from models_library.resource_tracker import (
    CreditClassification,
    CreditTransactionStatus,
)
from models_library.resource_tracker_license_purchases import (
    LicensePurchaseID,
    LicensePurchasesCreate,
)
from models_library.rest_ordering import OrderBy
from models_library.wallets import WalletID
from simcore_postgres_database.utils_repos import transaction_context
from sqlalchemy.ext.asyncio import AsyncEngine

from ..api.rest.dependencies import get_resource_tracker_db_engine
from ..models.credit_transactions import CreditTransactionCreate
from ..models.license_purchases import CreateLicensesPurchasesDB, LicensesPurchasesDB
from .modules.db import credit_transactions_db, license_purchases_db
from .modules.rabbitmq import RabbitMQClient, get_rabbitmq_client
from .utils import make_negative, sum_credit_transactions_and_publish_to_rabbitmq


async def list_license_purchases(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    filter_wallet_id: WalletID,
    offset: int = 0,
    limit: int = 20,
    order_by: OrderBy,
) -> LicensesPurchasesPage:
    total, license_purchases_list_db = await license_purchases_db.list_(
        db_engine,
        product_name=product_name,
        filter_wallet_id=filter_wallet_id,
        offset=offset,
        limit=limit,
        order_by=order_by,
    )
    return LicensesPurchasesPage(
        total=total,
        items=[
            LicensePurchaseGet(
                licensed_item_purchase_id=licensed_item_purchase_db.licensed_item_purchase_id,
                product_name=licensed_item_purchase_db.product_name,
                license_id=licensed_item_purchase_db.license_id,
                wallet_id=licensed_item_purchase_db.wallet_id,
                wallet_name=licensed_item_purchase_db.wallet_name,
                pricing_unit_cost_id=licensed_item_purchase_db.pricing_unit_cost_id,
                pricing_unit_cost=licensed_item_purchase_db.pricing_unit_cost,
                start_at=licensed_item_purchase_db.start_at,
                expire_at=licensed_item_purchase_db.expire_at,
                num_of_seats=licensed_item_purchase_db.num_of_seats,
                purchased_by_user=licensed_item_purchase_db.purchased_by_user,
                user_email=licensed_item_purchase_db.user_email,
                purchased_at=licensed_item_purchase_db.purchased_at,
                modified=licensed_item_purchase_db.modified,
            )
            for licensed_item_purchase_db in license_purchases_list_db
        ],
    )


async def get_license_purchase(
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    product_name: ProductName,
    licensed_item_purchase_id: LicensePurchaseID,
) -> LicensePurchaseGet:
    licensed_item_purchase_db: LicensesPurchasesDB = await license_purchases_db.get(
        db_engine,
        product_name=product_name,
        licensed_item_purchase_id=licensed_item_purchase_id,
    )

    return LicensePurchaseGet(
        licensed_item_purchase_id=licensed_item_purchase_db.licensed_item_purchase_id,
        product_name=licensed_item_purchase_db.product_name,
        license_id=licensed_item_purchase_db.license_id,
        wallet_id=licensed_item_purchase_db.wallet_id,
        wallet_name=licensed_item_purchase_db.wallet_name,
        pricing_unit_cost_id=licensed_item_purchase_db.pricing_unit_cost_id,
        pricing_unit_cost=licensed_item_purchase_db.pricing_unit_cost,
        start_at=licensed_item_purchase_db.start_at,
        expire_at=licensed_item_purchase_db.expire_at,
        num_of_seats=licensed_item_purchase_db.num_of_seats,
        purchased_by_user=licensed_item_purchase_db.purchased_by_user,
        user_email=licensed_item_purchase_db.user_email,
        purchased_at=licensed_item_purchase_db.purchased_at,
        modified=licensed_item_purchase_db.modified,
    )


async def create_license_purchase(
    rabbitmq_client: Annotated[RabbitMQClient, Depends(get_rabbitmq_client)],
    db_engine: Annotated[AsyncEngine, Depends(get_resource_tracker_db_engine)],
    *,
    data: LicensePurchasesCreate,
) -> LicensePurchaseGet:

    async with transaction_context(db_engine) as conn:
        item_purchase_create = CreateLicensesPurchasesDB(
            product_name=data.product_name,
            license_id=data.license_id,
            wallet_id=data.wallet_id,
            wallet_name=data.wallet_name,
            pricing_unit_cost_id=data.pricing_unit_cost_id,
            pricing_unit_cost=data.pricing_unit_cost,
            start_at=data.start_at,
            expire_at=data.expire_at,
            num_of_seats=data.num_of_seats,
            purchased_by_user=data.purchased_by_user,
            user_email=data.user_email,
            purchased_at=data.purchased_at,
        )

        licensed_item_purchase_db: LicensesPurchasesDB = (
            await license_purchases_db.create(
                db_engine, connection=conn, data=item_purchase_create
            )
        )

        # Deduct credits from credit_transactions table
        transaction_create = CreditTransactionCreate(
            product_name=data.product_name,
            wallet_id=data.wallet_id,
            wallet_name=data.wallet_name,
            pricing_plan_id=data.pricing_plan_id,
            pricing_unit_id=data.pricing_unit_id,
            pricing_unit_cost_id=data.pricing_unit_cost_id,
            user_id=data.purchased_by_user,
            user_email=data.user_email,
            osparc_credits=make_negative(data.pricing_unit_cost),
            transaction_status=CreditTransactionStatus.BILLED,
            transaction_classification=CreditClassification.DEDUCT_LICENSE_PURCHASE,
            service_run_id=None,
            payment_transaction_id=None,
            licensed_item_purchase_id=licensed_item_purchase_db.licensed_item_purchase_id,
            created_at=data.start_at,
            last_heartbeat_at=data.start_at,
        )
        await credit_transactions_db.create_credit_transaction(
            db_engine, connection=conn, data=transaction_create
        )

    # Publish wallet total credits to RabbitMQ
    await sum_credit_transactions_and_publish_to_rabbitmq(
        db_engine,
        rabbitmq_client=rabbitmq_client,
        product_name=data.product_name,
        wallet_id=data.wallet_id,
    )

    return LicensePurchaseGet(
        licensed_item_purchase_id=licensed_item_purchase_db.licensed_item_purchase_id,
        product_name=licensed_item_purchase_db.product_name,
        license_id=licensed_item_purchase_db.license_id,
        wallet_id=licensed_item_purchase_db.wallet_id,
        wallet_name=licensed_item_purchase_db.wallet_name,
        pricing_unit_cost_id=licensed_item_purchase_db.pricing_unit_cost_id,
        pricing_unit_cost=licensed_item_purchase_db.pricing_unit_cost,
        start_at=licensed_item_purchase_db.start_at,
        expire_at=licensed_item_purchase_db.expire_at,
        num_of_seats=licensed_item_purchase_db.num_of_seats,
        purchased_by_user=licensed_item_purchase_db.purchased_by_user,
        user_email=licensed_item_purchase_db.user_email,
        purchased_at=licensed_item_purchase_db.purchased_at,
        modified=licensed_item_purchase_db.modified,
    )
