
.PHONY: _check_venv_active
_check_venv_active:
	# Checking whether virtual environment was activated
	@python3 -c "import sys; assert sys.base_prefix!=sys.prefix"


.PHONY: install
install: _check_venv_active
	@cd ./../../../../services/storage && make install-dev && cd -
	@uv pip install -r requirements.txt


.PHONY: all
all: _check_venv_active
	@for file in *.py; do \
		python $$file; \
	done
