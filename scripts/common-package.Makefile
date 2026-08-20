# SHIM: content moved to scripts/makefiles/package.mk (naming convention: .mk = library).
# Kept so existing `include .../scripts/common-package.Makefile` references keep working.
# SEE scripts/makefiles/README.md
include $(dir $(lastword $(MAKEFILE_LIST)))makefiles/package.mk
