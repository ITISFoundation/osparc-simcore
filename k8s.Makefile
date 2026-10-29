SHELL := /bin/bash

#
# Vars
#

KIND_CLUSTER_NAME := simcore

MAKE := $(MAKE) --no-print-directory --silent

KUBECTL_VERSION := 1.36.1
KIND_VERSION := 0.32.0
HELMFILE_VERSION := 1.1.6

#
# Helpers
#

.require-%:
	@command -v $* >/dev/null || { echo "Missing required command: $*" >&2; exit 1; }

.helmfile-%: .require-helmfile .require-kubectl
	set -a; source .env-devel; set +a; \
	helmfile -f ./services/00-helmfile.local-cluster.yaml.gotmpl $* && \
	helmfile -f ./services/01-helmfile.local-ops.yaml.gotmpl $* && \
	helmfile -f ./services/02-helmfile.yaml.gotmpl $*

#
# Kubernetes Targets
#

.PHONY: helmfile-apply
helmfile-apply: .helmfile-apply

.PHONY: helmfile-diff
helmfile-diff: .helmfile-diff

.PHONY: helmfile-list
helmfile-list: .helmfile-list

.PHONY: helmfile-sync
helmfile-sync: .helmfile-sync

.PHONY: helmfile-destroy
helmfile-destroy: .helmfile-destroy

# kind gets no CNI from kind-config.yaml, so the nodes are `NotReady` until the
# cluster helmfile installs Calico: `make create-cluster && make helmfile-sync`
.PHONY: create-cluster
create-cluster: .require-kind
	kind create cluster --name $(KIND_CLUSTER_NAME) --config kind-config.yaml

.PHONY: destroy-cluster delete-cluster
destroy-cluster delete-cluster: .require-kind
	kind delete cluster --name $(KIND_CLUSTER_NAME)

#
# Developer targets
#

.PHONY: up-devel
up-devel:
	$(MAKE) -f k8s.Makefile helmfile-apply

.PHONY: down-devel
down-devel:
	$(MAKE) -f k8s.Makefile helmfile-destroy
