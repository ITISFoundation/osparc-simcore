# SHIM: content moved to scripts/makefiles/requirements.mk (naming convention: .mk = library).
# Kept so existing `include .../requirements/base.Makefile` references keep working.
# SEE scripts/makefiles/README.md
include $(dir $(lastword $(MAKEFILE_LIST)))../scripts/makefiles/requirements.mk
