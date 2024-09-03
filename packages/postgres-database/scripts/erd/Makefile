#
# ERD (Entity Relationship Diagram) is used to visualize these relationships
#
.DEFAULT_GOAL := help

PYTHON_VERSION=3.11.9

# locations
REPODIR := $(shell git rev-parse --show-toplevel)
PACKAGES_DIR := $(abspath $(REPODIR)/packages)
SERVICES_DIR := $(abspath $(REPODIR)/services)
PG_DIR := $(abspath $(PACKAGES_DIR)/postgres-database)

# tools
MAKE_C := $(MAKE) --directory


IMAGE_NAME:=local/postgres-database-scripts-erd:${PYTHON_VERSION}

# SEE https://medium.com/faun/set-current-host-user-for-docker-container-4e521cef9ffc
.PHONY: build
build build-nc: ## builds tooling image ${IMAGE_NAME}
	docker buildx build $(if $(findstring -nc,$@),--no-cache,) \
		--load \
		--build-arg PYTHON_VERSION="${PYTHON_VERSION}" \
		--tag ${IMAGE_NAME} .


.PHONY: shell
shell: build ## Opens shell in ${IMAGE_NAME}
	docker run -it \
		--workdir="/home/$(USER)" \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
		--volume="/etc/shadow:/etc/shadow:ro" \
		--volume=$(PG_DIR):/home/$(USER) \
		--user=$(shell id -u):$(shell id -g) \
		--entrypoint=/bin/bash \
		${IMAGE_NAME}


.PHONY: run
run: build ## Runs upgrade in a container [WARNING! UNDER DEV. USE CAREFULY]
	docker run -it \
		--workdir="/home/$(USER)" \
    --volume="/etc/group:/etc/group:ro" \
    --volume="/etc/passwd:/etc/passwd:ro" \
    --volume="/etc/shadow:/etc/shadow:ro" \
		--volume=$(PG_DIR):/home/$(USER) \
		--user=$(shell id -u):$(shell id -g) \
		--entrypoint=/bin/bash \
		${IMAGE_NAME} \
		-c "pip install -e .; python scripts/erd/cli.py"



.PHONY: help
# thanks to https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html
help: ## this colorful help
	@echo "Recipes for '$(notdir $(CURDIR))':"
	@echo ""
	@awk --posix 'BEGIN {FS = ":.*?## "} /^[[:alpha:][:space:]_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
	@echo ""
