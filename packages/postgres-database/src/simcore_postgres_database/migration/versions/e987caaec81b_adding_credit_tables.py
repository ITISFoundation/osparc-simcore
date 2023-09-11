"""adding credit tables

Revision ID: e987caaec81b
Revises: 6da4357ce10f
Create Date: 2023-08-09 16:59:21.001729+00:00

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "e987caaec81b"
down_revision = "6da4357ce10f"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table(
        "resource_tracker_pricing_plans",
        sa.Column("pricing_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.String(), server_default="", nullable=False),
        sa.Column(
            "classification",
            sa.Enum("TIER", name="pricingplanclassification"),
            nullable=False,
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("pricing_plan_id"),
    )
    op.create_index(
        op.f("ix_resource_tracker_pricing_plans_name"),
        "resource_tracker_pricing_plans",
        ["name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_pricing_plans_product_name"),
        "resource_tracker_pricing_plans",
        ["product_name"],
        unique=False,
    )
    op.create_table(
        "resource_tracker_service_runs",
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("service_run_id", sa.String(), nullable=False),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
        sa.Column("wallet_name", sa.String(), nullable=True),
        sa.Column("pricing_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("pricing_detail_id", sa.BigInteger(), nullable=False),
        sa.Column("simcore_user_agent", sa.String(), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=True),
        sa.Column("project_id", sa.String(), nullable=False),
        sa.Column("project_name", sa.String(), nullable=True),
        sa.Column("node_id", sa.String(), nullable=False),
        sa.Column("node_name", sa.String(), nullable=True),
        sa.Column("service_key", sa.String(), nullable=False),
        sa.Column("service_version", sa.String(), nullable=False),
        sa.Column(
            "service_type",
            sa.Enum(
                "COMPUTATIONAL_SERVICE",
                "DYNAMIC_SERVICE",
                name="resourcetrackerservicetype",
            ),
            nullable=False,
        ),
        sa.Column(
            "service_resources", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "service_additional_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "service_run_status",
            sa.Enum(
                "RUNNING", "SUCCESS", "ERROR", name="resourcetrackerservicerunstatus"
            ),
            nullable=False,
        ),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("product_name", "service_run_id"),
    )
    op.create_table(
        "resource_tracker_wallets_credit_transactions",
        sa.Column("transaction_id", sa.BigInteger(), nullable=False),
        sa.Column("product_name", sa.String(), nullable=False),
        sa.Column("wallet_id", sa.BigInteger(), nullable=False),
        sa.Column("wallet_name", sa.String(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("user_email", sa.String(), nullable=False),
        sa.Column("credits", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column(
            "transaction_status",
            sa.Enum(
                "PENDING",
                "BILLED",
                "NOT_BILLED",
                "REQUIRES_MANUAL_REVIEW",
                name="transactionbillingstatus",
            ),
            nullable=True,
        ),
        sa.Column(
            "transaction_classification",
            sa.Enum(
                "ADD_WALLET_TOP_UP",
                "DEDUCT_SERVICE_RUN",
                name="transactionclassification",
            ),
            nullable=True,
        ),
        sa.Column("service_run_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("transaction_id"),
    )
    op.create_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_product_name"),
        "resource_tracker_wallets_credit_transactions",
        ["product_name"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_service_run_id"),
        "resource_tracker_wallets_credit_transactions",
        ["service_run_id"],
        unique=False,
    )
    op.create_index(
        op.f(
            "ix_resource_tracker_wallets_credit_transactions_transaction_classification"
        ),
        "resource_tracker_wallets_credit_transactions",
        ["transaction_classification"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_transaction_status"),
        "resource_tracker_wallets_credit_transactions",
        ["transaction_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_wallet_id"),
        "resource_tracker_wallets_credit_transactions",
        ["wallet_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_wallet_name"),
        "resource_tracker_wallets_credit_transactions",
        ["wallet_name"],
        unique=False,
    )
    op.create_table(
        "resource_tracker_pricing_details",
        sa.Column("pricing_detail_id", sa.BigInteger(), nullable=False),
        sa.Column("pricing_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("unit_name", sa.String(), nullable=False),
        sa.Column("cost_per_unit", sa.Numeric(precision=3, scale=2), nullable=False),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "specific_info", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pricing_plan_id"],
            ["resource_tracker_pricing_plans.pricing_plan_id"],
            name="fk_resource_tracker_pricing_details_pricing_plan_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("pricing_detail_id"),
    )
    op.create_index(
        op.f("ix_resource_tracker_pricing_details_pricing_plan_id"),
        "resource_tracker_pricing_details",
        ["pricing_plan_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_resource_tracker_pricing_details_unit_name"),
        "resource_tracker_pricing_details",
        ["unit_name"],
        unique=False,
    )
    op.create_table(
        "resource_tracker_pricing_plan_to_service",
        sa.Column("pricing_plan_id", sa.BigInteger(), nullable=False),
        sa.Column("service_key", sa.String(), nullable=False),
        sa.Column("service_version", sa.String(), nullable=False),
        sa.Column(
            "created",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "modified",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["pricing_plan_id"],
            ["resource_tracker_pricing_plans.pricing_plan_id"],
            name="fk_resource_tracker_pricing_details_pricing_plan_id",
            onupdate="CASCADE",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "service_key",
            "service_version",
            name="resource_tracker_pricing_plan_to_service__service_unique_key",
        ),
    )
    op.create_index(
        op.f("ix_resource_tracker_pricing_plan_to_service_pricing_plan_id"),
        "resource_tracker_pricing_plan_to_service",
        ["pricing_plan_id"],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(
        op.f("ix_resource_tracker_pricing_plan_to_service_pricing_plan_id"),
        table_name="resource_tracker_pricing_plan_to_service",
    )
    op.drop_table("resource_tracker_pricing_plan_to_service")
    op.drop_index(
        op.f("ix_resource_tracker_pricing_details_unit_name"),
        table_name="resource_tracker_pricing_details",
    )
    op.drop_index(
        op.f("ix_resource_tracker_pricing_details_pricing_plan_id"),
        table_name="resource_tracker_pricing_details",
    )
    op.drop_table("resource_tracker_pricing_details")
    op.drop_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_wallet_name"),
        table_name="resource_tracker_wallets_credit_transactions",
    )
    op.drop_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_wallet_id"),
        table_name="resource_tracker_wallets_credit_transactions",
    )
    op.drop_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_transaction_status"),
        table_name="resource_tracker_wallets_credit_transactions",
    )
    op.drop_index(
        op.f(
            "ix_resource_tracker_wallets_credit_transactions_transaction_classification"
        ),
        table_name="resource_tracker_wallets_credit_transactions",
    )
    op.drop_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_service_run_id"),
        table_name="resource_tracker_wallets_credit_transactions",
    )
    op.drop_index(
        op.f("ix_resource_tracker_wallets_credit_transactions_product_name"),
        table_name="resource_tracker_wallets_credit_transactions",
    )
    op.drop_table("resource_tracker_wallets_credit_transactions")
    op.drop_table("resource_tracker_service_runs")
    op.drop_index(
        op.f("ix_resource_tracker_pricing_plans_product_name"),
        table_name="resource_tracker_pricing_plans",
    )
    op.drop_index(
        op.f("ix_resource_tracker_pricing_plans_name"),
        table_name="resource_tracker_pricing_plans",
    )
    op.drop_table("resource_tracker_pricing_plans")

    sa.Enum(name="transactionbillingstatus").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="transactionclassification").drop(op.get_bind(), checkfirst=False)
    # ### end Alembic commands ###
