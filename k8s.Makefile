SHELL := /bin/bash

#
# Vars
#

KIND_CLUSTER_NAME := simcore

MAKE := $(MAKE) --no-print-directory --silent

#
# Helpers
#

.helmfile-%:
	set -a; source .env-devel; set +a; \
	helmfile -f ./services/helmfile.ops.yaml.gotmpl $*

helmfile-apply: .helmfile-apply
helmfile-diff: .helmfile-diff

#
# Targets
#

.PHONY: create-cluster
create-cluster:
	kind create cluster --name $(KIND_CLUSTER_NAME)

.PHONY: up-devel
up-devel: create-cluster
	$(MAKE) .helmfile-apply
