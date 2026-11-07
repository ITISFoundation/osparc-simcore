#
# Local Kubernetes development environment: a kind cluster plus the local
# helmfile charts.
#

.DEFAULT_GOAL := help

_K8S_DIR := $(dir $(lastword $(MAKEFILE_LIST)))
include $(_K8S_DIR)../scripts/makefiles/globals.mk
include $(REPO_BASE_DIR)/scripts/makefiles/help.mk
include $(REPO_BASE_DIR)/scripts/makefiles/k8s.mk

# VARIABLES ----------------------------------------------

KIND_CLUSTER_NAME := simcore

# TARGETS ------------------------------------------------

##@ Cluster

.PHONY: create-cluster
create-cluster: _require-valid-kind ## Creates Kubernetes cluster
	kind create cluster --name $(KIND_CLUSTER_NAME) --config $(_K8S_DIR)kind-config.yaml

.PHONY: delete-cluster destroy-cluster
delete-cluster destroy-cluster: _require-valid-kind ## Deletes Kubernetes cluster
	kind delete cluster --name $(KIND_CLUSTER_NAME)

##@ Development

.PHONY: down-devel up-devel
down-devel: helmfile-destroy ## Destroy services
up-devel: helmfile-apply ## Deploys services

##@ Helmfile

.PHONY: helmfile-apply
helmfile-apply: .helmfile-apply ## Deploy services

.PHONY: helmfile-destroy
helmfile-destroy: .helmfile-destroy ## Destroy services

.PHONY: helmfile-diff
helmfile-diff: .helmfile-diff ## Shows changes in services

.PHONY: helmfile-lint
helmfile-lint: .helmfile-lint ## Lints all services

.PHONY: helmfile-list
helmfile-list: .helmfile-list ## Lists all services

.PHONY: helmfile-sync
helmfile-sync: .helmfile-sync # Only use if you know why

.PHONY: helmfile-template
helmfile-template: .helmfile-template ## Renders manifests of all services
