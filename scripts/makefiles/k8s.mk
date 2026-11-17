#
# LOCAL KUBERNETES helpers for the kind cluster and the local helmfile charts.
#

#
# Versions
#

KUBECONFORM_VERSION := 0.8.0
KIND_VERSION := 0.32.0
HELMFILE_VERSION := 1.1.6
HELM_VERSION := 3.22.1

#
# Helmfile configuration
#

HELMFILE_ENV := HELM_DIFF_OUTPUT_CONTEXT=5
HELMFILE_GLOBAL_FLAGS := --environment local
HELMFILE_COMMAND_FLAGS ?=

#
# Helper targets/functions
#

# run_helmfile <helmfile_file> <command>
# Example: $(call run_helmfile,services/helmfile.yaml.gotmpl,lint)
define run_helmfile
    cd $(REPO_BASE_DIR) || exit 1; \
    set -a; source .env-devel; source k8s/.env-devel-k8s-override; set +a; \
    $(HELMFILE_ENV) helmfile $(HELMFILE_GLOBAL_FLAGS) -f $(1) $(2) $(HELMFILE_COMMAND_FLAGS)
endef

.PHONY: _require-valid-helm
_require-valid-helm:
	$(call verify_tool_installation,helm,$(HELM_VERSION),helm version --short)

.PHONY: _require-valid-helmfile
_require-valid-helmfile:
	$(call verify_tool_installation,helmfile,$(HELMFILE_VERSION),helmfile --version)

.PHONY: _require-valid-kind
_require-valid-kind:
	$(call verify_tool_installation,kind,$(KIND_VERSION),kind --version)

.PHONY: _require-valid-kubeconform
_require-valid-kubeconform:
	$(call verify_tool_installation,kubeconform,$(KUBECONFORM_VERSION),kubeconform -v)

.helmfile-%: _require-valid-helm _require-valid-helmfile
	@$(MAKE) .helmfile-ops-$*
	@$(MAKE) .helmfile-simcore-$*

.helmfile-ops-%: _require-valid-helm _require-valid-helmfile
	@$(call run_helmfile,services/helmfile.local-ops.yaml.gotmpl,$*)

.helmfile-simcore-%: _require-valid-helm _require-valid-helmfile
	@$(call run_helmfile,services/helmfile.yaml.gotmpl,$*)

.PHONY: .init-swarm
.init-swarm:
	@# init docker swarm for dv2 to start. we are not going to use it
	@swarm_state=$$(docker info --format '{{.Swarm.LocalNodeState}}') || exit 1; \
	if [ "$$swarm_state" = "inactive" ]; then \
		docker swarm init --advertise-addr 127.0.0.1; \
	fi
