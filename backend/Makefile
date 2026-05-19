PYTHON ?= python
VENV   ?= .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

.PHONY: help venv install protos test lint type server clean

help:
	@echo "Chaos One backend targets:"
	@echo "  make venv      create local virtualenv"
	@echo "  make install   install package with dev extras"
	@echo "  make protos    compile chaos_one.proto into gRPC stubs"
	@echo "  make test      run pytest"
	@echo "  make lint      ruff check + format check"
	@echo "  make type      mypy strict"
	@echo "  make server    run gRPC server on 127.0.0.1:50051"
	@echo "  make clean     remove venv and generated stubs"

venv:
	$(PYTHON) -m venv $(VENV)

install: venv
	$(PIP) install --upgrade pip
	$(PIP) install -e ".[dev]"

protos:
	$(PY) -m grpc_tools.protoc \
		-I proto \
		--python_out=src/chaos_backend/generated \
		--grpc_python_out=src/chaos_backend/generated \
		proto/chaos_one.proto
	@touch src/chaos_backend/generated/__init__.py
	@bash scripts/generate_protos.sh > /dev/null
	@echo "protos: regenerated"

test:
	$(VENV)/bin/pytest -q

lint:
	$(VENV)/bin/ruff check src tests
	$(VENV)/bin/ruff format --check src tests

type:
	$(VENV)/bin/mypy src

server:
	$(VENV)/bin/chaos-backend

clean:
	rm -rf $(VENV)
	rm -rf src/chaos_backend/generated/chaos_one_pb2*.py
