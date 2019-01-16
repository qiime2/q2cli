.PHONY: all lint test install dev clean distclean

PYTHON ?= python
PREFIX ?= $(CONDA_PREFIX)

all: ;

lint:
	q2lint
	flake8

test: all
	QIIMETEST= nosetests

install: all
	$(PYTHON) setup.py install && \
	mkdir -p $(PREFIX)/etc/conda/activate.d && \
	cp hooks/50_activate_q2cli_tab_completion.sh $(PREFIX)/etc/conda/activate.d/

dev: all
	pip install -e .

clean: distclean

distclean: ;
