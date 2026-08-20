#
# Version bump targets (bump2version).
#
# LIBRARY (.mk): include-only, not a directly-invoked entry point.
# SEE scripts/makefiles/README.md for conventions.
#

.PHONY: version-patch version-minor version-major
version-patch: ## commits version with bug fixes not affecting the cookiecuter config
	$(_bumpversion)
version-minor: ## commits version with backwards-compatible API addition or changes (i.e. can replay)
	$(_bumpversion)
version-major: ## commits version with backwards-INcompatible addition or changes
	$(_bumpversion)


define _bumpversion
	# Upgrades as $(subst version-,,$@) version, commits and tags
	@bump2version --verbose --list $(subst version-,,$@)
endef
