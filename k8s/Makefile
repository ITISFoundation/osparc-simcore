#
# Local Kubernetes development environment: a kind cluster plus the local
# helmfile charts.
#

.DEFAULT_GOAL := help

REPO_BASE_DIR := $(shell git rev-parse --show-toplevel)

include $(REPO_BASE_DIR)/scripts/makefiles/help.mk
include $(REPO_BASE_DIR)/scripts/makefiles/globals.mk
include $(REPO_BASE_DIR)/scripts/makefiles/k8s.mk

# VARIABLES ----------------------------------------------

KIND_CLUSTER_NAME := simcore

# TARGETS ------------------------------------------------

##@ Environment

.PHONY: install-tools
install-tools: ## Installs k8s tools
	@cd $(CURDIR) && mise trust --quiet && mise install

##@ Cluster

.PHONY: create-cluster
create-cluster: .init-swarm ## Creates Kubernetes cluster
	@cd $(CURDIR) && \
	kind create cluster --name $(KIND_CLUSTER_NAME) --config kind-config.yaml

.PHONY: delete-cluster
delete-cluster: ## Deletes Kubernetes cluster
	kind delete cluster --name $(KIND_CLUSTER_NAME)

.PHONY: recreate-cluster
recreate-cluster: ## Recreates Kubernetes cluster
	@$(MAKE) delete-cluster
	@$(MAKE) create-cluster

.PHONY: load-images-into-cluster
load-images-into-cluster: ## Loads simcore images into Kubernetes cluster
	@images=$$(docker images --filter 'reference=local/*:development' --format '{{.Repository}}:{{.Tag}}'); \
	test -n "$$images" || { echo "no local/{service}:development images. Build them first with 'make build-devel'."; exit 1; }; \
	kind load docker-image --name $(KIND_CLUSTER_NAME) $$images

##@ Services

.PHONY: down-devel up-devel
down-devel: helmfile-destroy ## Destroys services
up-devel: ## Deploys services
	@$(MAKE) load-images-into-cluster
	@$(MAKE) helmfile-apply

.PHONY: helmfile-apply helmfile-ops-apply helmfile-simcore-apply
helmfile-apply: .helmfile-apply ## Deploys all services
helmfile-ops-apply: .helmfile-ops-apply ## Deploys ops services
helmfile-simcore-apply: .helmfile-simcore-apply ## Deploys simcore services

.PHONY: helmfile-destroy helmfile-ops-destroy helmfile-simcore-destroy
helmfile-destroy: .helmfile-destroy ## Destroys all services
helmfile-ops-destroy: .helmfile-ops-destroy ## Destroys ops services
helmfile-simcore-destroy: .helmfile-simcore-destroy ## Destroys simcore services

.PHONY: helmfile-diff helmfile-ops-diff helmfile-simcore-diff
helmfile-diff: .helmfile-diff ## Shows changes in all services
helmfile-ops-diff: .helmfile-ops-diff ## Shows changes in ops services
helmfile-simcore-diff: .helmfile-simcore-diff ## Shows changes in simcore services

##@ Tests

.PHONY: helm-unittest
helm-unittest: HELM_UNITTEST_BIN := untt # installed via mise
helm-unittest: ## Runs helm-unittest tests of the simcore-service chart
	@$(HELM_UNITTEST_BIN) --color --strict $(REPO_BASE_DIR)/charts/simcore-service

kubeconform: guard-TEMPLATES_DIR guard-KUBERNETES_VERSION
kubeconform: ## Validates Kubernetes manifests with kubeconform
	@kubeconform \
		-schema-location default \
		-schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
		-kubernetes-version $(KUBERNETES_VERSION) \
		-strict \
		-verbose \
		$(TEMPLATES_DIR)

##@ Lint

.PHONY: helmfile-lint helmfile-ops-lint helmfile-simcore-lint
helmfile-lint: .helmfile-lint ## Lints all services
helmfile-ops-lint: .helmfile-ops-lint ## Lints ops services
helmfile-simcore-lint: .helmfile-simcore-lint ## Lints simcore services

##@ Misc

.PHONY: helmfile-list helmfile-ops-list helmfile-simcore-list
helmfile-list: .helmfile-list ## Lists all services
helmfile-ops-list: .helmfile-ops-list ## Lists ops services
helmfile-simcore-list: .helmfile-simcore-list ## Lists simcore services

.PHONY: helmfile-sync helmfile-ops-sync helmfile-simcore-sync
helmfile-sync: .helmfile-sync # Only use if you know why
helmfile-ops-sync: .helmfile-ops-sync # Only use if you know why
helmfile-simcore-sync: .helmfile-simcore-sync # Only use if you know why

.PHONY: helmfile-template helmfile-ops-template helmfile-simcore-template
helmfile-template: .helmfile-template ## Renders manifests of all services
helmfile-ops-template: .helmfile-ops-template ## Renders manifests of ops services
helmfile-simcore-template: .helmfile-simcore-template ## Renders manifests of simcore services
