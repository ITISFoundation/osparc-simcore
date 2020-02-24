
.PHONY: install .check-venv-active

.check-venv-active: # prevents from installing in system python
	# checking if active virtual environment
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"

install: .check-venv-active
	pip install -r requirements.txt


.PHONY: up-locust down
NUM_CLIENTS = 1000
HATCH_RATE = 2

up-locust: .check-venv-active
	# Starting http://localhost:8089/
	locust --csv-full-history --locustfile=locust_files/basic.py

down:
	pkill locust


.PHONY: tables
PG_PUBLISHED_PORT := $(shell docker inspect simcore_postgres --format "{{(index .Endpoint.Ports 0).PublishedPort}}")

define inject-data-in-db =
	@PGPASSWORD=adminadmin psql --host localhost \
								--port $(PG_PUBLISHED_PORT) \
								--user scu \
								--dbname simcoredb \
								--command "\copy $(1) from 'data/$(2)' csv header;";
endef

tables: ## injects test projects and user in databass
	$(call inject-data-in-db,users,users.csv)
	$(call inject-data-in-db,projects,projects.csv)
