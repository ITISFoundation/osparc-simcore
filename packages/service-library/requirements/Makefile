objects = $(wildcard *.in)
outputs := $(objects:.in=.txt)

.PHONY: all
# target: all – pip-compiles all requirements/*.in -> requirements/*.txt
all: $(outputs)

%.txt: %.in
	pip-compile --output-file $@ $<

ci-base.txt: base.txt

.PHONY: check
# target: check – Checks whether pip-compile is installed
check:
	@which pip-compile > /dev/null

.PHONY: clean
# target: clean – Cleans all requirements/*.txt (except dev.txt)
clean: check
	rm $(outputs)

.PHONY: help
# target: help – Display all callable targets
help:
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| sed -r "s/^\s*#\s*target\s*:\s*//g"
	@echo
