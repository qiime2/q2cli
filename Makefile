.PHONY: all lint test install dev clean distclean

all: ;

lint:
	q2lint
	flake8

test: all
	QIIMETEST= nosetests

install: all
	python setup.py install && \
	mkdir -p $(CONDA_PREFIX)/etc/conda/activate.d && \
	cp hooks/50_activate_q2cli_tab_completion.sh $(CONDA_PREFIX)/etc/conda/activate.d/

dev: all
	pip install -e .

clean: distclean

distclean: ;
