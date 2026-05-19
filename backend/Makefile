PYTHON ?= python
VENV   ?= .venv
PIP    := $(VENV)/bin/pip
PY     := $(VENV)/bin/python

.PHONY: help venv install protos test lint type server demo bench ci all clean

help:
	@echo "Chaos One backend targets:"
	@echo "  make install   create venv and install package with dev extras"
	@echo "  make protos    compile chaos_one.proto into gRPC stubs"
	@echo "  make lint      ruff check + format check"
	@echo "  make type      mypy strict"
	@echo "  make test      pytest with coverage"
	@echo "  make ci        run the same gates GitHub Actions runs"
	@echo "  make bench     run the micro-benchmark harness"
	@echo "  make demo      run chaos-backend-cli demo end-to-end"
	@echo "  make server    run the gRPC server on 127.0.0.1:50051"
	@echo "  make all       install + protos + ci"
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
	$(VENV)/bin/ruff check src tests benchmarks
	$(VENV)/bin/ruff format --check src tests benchmarks

type:
	$(VENV)/bin/mypy src

ci: lint type test
	@echo "ci: green"

all: install protos ci
	@echo "all: ready"

server:
	$(VENV)/bin/chaos-backend

demo:
	$(VENV)/bin/chaos-backend-cli demo --scenario peer_salvo --seed 42 --tracks 4

bench:
	$(PY) -m benchmarks.run_all

clean:
	rm -rf $(VENV)
	rm -rf src/chaos_backend/generated/chaos_one_pb2*.py
