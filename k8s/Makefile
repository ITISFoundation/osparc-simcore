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
	cd $(_K8S_DIR) && kind create cluster --name $(KIND_CLUSTER_NAME) --config kind-config.yaml

.PHONY: delete-cluster destroy-cluster
delete-cluster destroy-cluster: _require-valid-kind ## Deletes Kubernetes cluster
	kind delete cluster --name $(KIND_CLUSTER_NAME)

.PHONY: load-images
load-images-into-cluster: _require-valid-kind ## Loads simcore images into Kubernetes cluster
	@images=$$(docker images --filter 'reference=local/*:development' --format '{{.Repository}}:{{.Tag}}'); \
	test -n "$$images" || { echo "no local/{service}:development images. Build them first with 'make build-devel'."; exit 1; }; \
	kind load docker-image --name $(KIND_CLUSTER_NAME) $$images

.PHONY: recreate-cluster
recreate-cluster: ## Recreates Kubernetes cluster
	@$(MAKE) delete-cluster
	@$(MAKE) create-cluster

##@ Development

.PHONY: down-devel up-devel
down-devel: helmfile-destroy ## Destroy services
up-devel: ## Deploys services
	@$(MAKE) load-images-into-cluster
	@$(MAKE) helmfile-apply

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
