# SHIM: content moved to scripts/makefiles/templates.mk (naming convention: .mk = library).
# Kept so existing `include .../scripts/common-templates.Makefile` references keep working.
# SEE scripts/makefiles/README.md
include $(dir $(lastword $(MAKEFILE_LIST)))makefiles/templates.mk
