# Example for database migration

Illustrates the workflow for database migration using `alembic`

There are two folders:
 - models: contains definition of tables in different stages
 - migration: will contain files needed for migration, needs to be creted first. All `alembic` commands must be started in this directory.

## Step 1 Initialize

```bash
docker-compose up -d
pip install alembic
cd migration
alembic init alembic
````

This starts the database and creates an initial configuration for the migration.
We want to have a baseline state that basically contains only the table defintions.

```bash
alembic revision -m "baseline"
```

This creates a file `uid_baseline.py` in `alembic/versions`.

Go there and edit manually
```python

"""baseline

Revision ID: 100559f72c66
Revises:
Create Date: 2018-07-11 14:28:59.084794

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '100559f72c66'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
     op.create_table(
        'A',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(), nullable=False))

    op.create_table(
        'B',
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('name', sa.String(), nullable=False))


def downgrade():
    op.drop_table('A')
    op.drop_table('B')
```

Edit the file `alembic.ini` for the correct db url

```
sqlalchemy.url = postgresql+psycopg2://test:test@localhost:5432/test
```

Upgrade the database to the current state

```bash
alembic upgrade head
```

Go and check `localhost:18080`


## Step 2 Track changes

From now on we want to automatically track changes in the models.
Edit the file `migration/alembic/env.py` and import all models that shall be tracked. Obviously those guys need to be in the path.
Also change

```python
target_metadata = Base.metadata
```

```python

from __future__ import with_statement
from alembic import context
from sqlalchemy import engine_from_config, pool
from logging.config import fileConfig

from base import Base
from a import A
from b import B

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

```

Now start changing the schemas:

Copy `a.py.1` to `a.py` and let `alembic` do its magic

```bash
alembic revision --autogenerate -m "Adds new thing to A"
```
This creates an new script `uuid_adds_new_thing_to_a.py`

Upgrade can be done with

```bash
alembic upgrade head
```

Go and check `localhost:18080`

Copy `b.py.1` to `b.py` and let `alembic` do its magic
```bash
alembic revision --autogenerate -m "Adds new thing to B"
```
This creates an new script `uuid_adds_new_thing_to_b.py`

Upgrade can be done with

```bash
alembic upgrade head
```

Go and check `localhost:18080`

From now on you can do the following

```bash
alembic upgrade +1
alembic downgrade -1
alembic downgrade -2
```
