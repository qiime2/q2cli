.PHONY: all lint test install dev clean distclean

PYTHON ?= python
PREFIX ?= $(CONDA_PREFIX)

all: ;

lint:
	q2lint
	flake8

test: all
	QIIMETEST= pytest

# install pytest-xdist plugin for the `-n auto` argument.
mystery-stew: all
	MYSTERY_STEW= pytest -k mystery_stew -n auto

install: all
	$(PYTHON) setup.py install && \
	mkdir -p $(PREFIX)/etc/conda/activate.d && \
	cp hooks/50_activate_q2cli_tab_completion.sh $(PREFIX)/etc/conda/activate.d/

dev: all
	pip install -e . && \
	mkdir -p $(PREFIX)/etc/conda/activate.d && \
	cp hooks/50_activate_q2cli_tab_completion.sh $(PREFIX)/etc/conda/activate.d/

clean: distclean

distclean: ;
