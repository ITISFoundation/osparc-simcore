# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


import pytest
import sqlalchemy as sa
from simcore_postgres_database.models._common import RefActions
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.models.tags_access_rights import tags_access_rights
from simcore_postgres_database.models.users import users


@pytest.mark.skip(reason="DEV only")
def test_migration_downgrade_script():
    # NOTE: This test keeps for the record how the downgrade expression in
    # migration/versions/3aa309471ff8_add_tag_to_groups_table_and_rm_tag_user_.py
    # was deduced.
    old_tags = sa.Table(
        "old_tags",
        metadata,
        sa.Column("id", sa.BigInteger, nullable=False, primary_key=True),
        sa.Column(
            "user_id",
            sa.BigInteger,
            sa.ForeignKey(
                "users.id", onupdate=RefActions.CASCADE, ondelete=RefActions.CASCADE
            ),
            nullable=False,
        ),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("description", sa.String, nullable=True),
        sa.Column("color", sa.String, nullable=False),
    )

    j = users.join(
        tags_access_rights, tags_access_rights.c.group_id == users.c.primary_gid
    )

    scalar_subq = (
        sa.select(users.c.id)
        .select_from(j)
        .where(old_tags.c.id == tags_access_rights.c.tag_id)
        .scalar_subquery()
    )

    update_stmt = old_tags.update().values(user_id=scalar_subq)

    assert str(update_stmt).split("\n") == [
        "UPDATE old_tags SET user_id=(SELECT users.id ",
        "FROM users JOIN tags_access_rights ON tags_access_rights.group_id = users.primary_gid ",
        "WHERE old_tags.id = tags_access_rights.tag_id)",
    ]
