objects = $(wildcard *.in)
outputs := $(objects:.in=.txt)

.PHONY: all
# target: all – pip-compiles all requirements/*.in -> requirements/*.txt
all: $(outputs)

%.txt: %.in
	pip-compile --output-file $@ $<

ci-base.txt: base.txt

# avoids test.txt since it is NOT used
test.txt: test.in


.PHONY: check
# target: check – Checks whether pip-compile is installed
check:
	@which pip-compile > /dev/null

.PHONY: clean
# target: clean – Cleans all requirements/*.txt having a *.in counterpart
clean: check
	@find . -type f -name '*.txt' -not -name 'dev.txt' -not -name 'ci.txt' -not -name 'prod.txt' -print0 | xargs -0 rm --

.PHONY: help
# target: help – Display all callable targets
help:
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| sed -r "s/^\s*#\s*target\s*:\s*//g"
	@echo
