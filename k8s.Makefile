SHELL := /bin/bash

#
# Vars
#

KIND_CLUSTER_NAME := simcore

MAKE := $(MAKE) --no-print-directory --silent

#
# Helpers
#

.require-%:
	@command -v $* >/dev/null || { echo "Missing required command: $*" >&2; exit 1; }

.helmfile-%: .require-helmfile
	set -a; source .env-devel; set +a; \
	helmfile -f ./services/helmfile.ops.yaml.gotmpl $*


#
# Kubernetes Targets
#

.PHONY: helmfile-apply
helmfile-apply: .helmfile-apply

.PHONY: helmfile-diff
helmfile-diff: .helmfile-diff

.PHONY: helmfile-destroy
helmfile-destroy: .helmfile-destroy

.PHONY: helmfile-list
helmfile-list: .helmfile-list

.PHONY: create-cluster
create-cluster: .require-kind
	kind create cluster --name $(KIND_CLUSTER_NAME) --config kind-config.yaml

.PHONY: destroy-cluster
destroy-cluster: .require-kind
	kind delete cluster --name $(KIND_CLUSTER_NAME)

#
# Developer targets
#

.PHONY: up-devel
up-devel: create-cluster
	$(MAKE) helmfile-apply

.PHONY: down-devel
down-devel: destroy-cluster
