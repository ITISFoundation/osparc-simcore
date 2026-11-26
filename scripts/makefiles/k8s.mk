#
# LOCAL KUBERNETES helpers for the kind cluster and the local helmfile charts.
#

#
# Vars
#

K8S_DIR = $(REPO_BASE_DIR)/k8s

#
# Helmfile configuration
#

HELMFILE_ENV := HELM_DIFF_OUTPUT_CONTEXT=5
HELMFILE_GLOBAL_FLAGS := --environment local
HELMFILE_COMMAND_FLAGS ?=

#
# utils
#

.PHONY: _require-mise
_require-mise:
	@if ! command -v mise >/dev/null 2>&1; then \
		echo "'mise' is not installed. Install it to continue."; \
		echo "See https://mise.jdx.dev/"; \
		exit 1; \
	fi

# run_helmfile <helmfile_file> <command>
# Example: $(call run_helmfile,$(REPO_BASE_DIR)/services/helmfile.yaml.gotmpl,lint)
define run_helmfile
    cd $(K8S_DIR) || exit 1; \
    set -a; source $(REPO_BASE_DIR)/.env-devel; source $(K8S_DIR)/.env-devel-k8s-override; set +a; \
    $(HELMFILE_ENV) helmfile $(HELMFILE_GLOBAL_FLAGS) -f $(1) $(2) $(HELMFILE_COMMAND_FLAGS)
endef

#
# helmfile internal
#

.helmfile-%:
	@$(MAKE) .helmfile-ops-$*
	@$(MAKE) .helmfile-simcore-$*

.helmfile-ops-%:
	@$(call run_helmfile,$(REPO_BASE_DIR)/services/helmfile.local-ops.yaml.gotmpl,$*)

.helmfile-simcore-%:
	@$(call run_helmfile,$(REPO_BASE_DIR)/services/helmfile.yaml.gotmpl,$*)

.PHONY: .init-swarm
.init-swarm:
	@# init docker swarm for dv2 to start. we are not going to use it
	@swarm_state=$$(docker info --format '{{.Swarm.LocalNodeState}}') || exit 1; \
	if [ "$$swarm_state" = "inactive" ]; then \
		docker swarm init --advertise-addr 127.0.0.1; \
	fi
