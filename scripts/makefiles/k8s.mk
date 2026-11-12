#
# LOCAL KUBERNETES helpers for the kind cluster and the local helmfile charts.
#

KUBECTL_VERSION := 1.36.1
KIND_VERSION := 0.32.0
HELMFILE_VERSION := 1.1.6
HELM_VERSION := 3.20.2

HELMFILE := HELM_DIFF_OUTPUT_CONTEXT=5 helmfile --environment local

.PHONY: _require-valid-helm
_require-valid-helm:
	$(call verify_tool_installation,helm,$(HELM_VERSION),helm version --short)

.PHONY: _require-valid-helmfile
_require-valid-helmfile:
	$(call verify_tool_installation,helmfile,$(HELMFILE_VERSION),helmfile --version)

.PHONY: _require-valid-kubectl
_require-valid-kubectl:
	$(call verify_tool_installation,kubectl,$(KUBECTL_VERSION),kubectl version --client)

.PHONY: _require-valid-kind
_require-valid-kind:
	$(call verify_tool_installation,kind,$(KIND_VERSION),kind --version)

.helmfile-%: _require-valid-helm _require-valid-helmfile _require-valid-kubectl
	cd $(REPO_BASE_DIR) || exit 1; \
	set -a; source .env-devel; source k8s/.env-devel-k8s-override; set +a; \
	$(HELMFILE) -f services/helmfile.local-ops.yaml.gotmpl $* && \
	$(HELMFILE) -f services/helmfile.yaml.gotmpl $*
