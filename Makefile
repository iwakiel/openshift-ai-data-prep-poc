NAMESPACE       ?= mlops-poc
IMAGE_REGISTRY  ?= image-registry.openshift-image-registry.svc:5000
IMAGE_NAME      ?= retail-data-prep
IMAGE_TAG       ?= latest
IMAGE           := $(IMAGE_REGISTRY)/$(NAMESPACE)/$(IMAGE_NAME):$(IMAGE_TAG)

.DEFAULT_GOAL := help

help:
	@echo "Usage: make <target>"
	@echo ""
	@echo "  install          Install the package locally in editable mode"
	@echo "  install-dev      Install with dev dependencies"
	@echo "  build-image      Build the pipeline component Docker image"
	@echo "  push-image       Push the image to the OpenShift registry"
	@echo "  verify-env       Run the RHOAI environment verification script"
	@echo "  generate-data    Generate synthetic retail banking data"
	@echo "  compile-pipeline Compile the KFP pipeline to YAML"
	@echo "  run-tests        Run unit tests with coverage"
	@echo "  lint             Run flake8 and black check"
	@echo "  format           Auto-format code with black and isort"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev,pipeline]"

build-image:
	docker build -t $(IMAGE) .

push-image:
	docker push $(IMAGE)

verify-env:
	bash scripts/verify_rhoai_env.sh --namespace $(NAMESPACE)

generate-data:
	python -m src.data_generation.customers --records 500000
	python -m src.data_generation.transactions \
		--records 2000000 \
		--customers-path /tmp/customers.parquet

compile-pipeline:
	python -m src.pipeline.banking_pipeline --compile-only

run-tests:
	pytest tests/ -v --cov=src --cov-report=term-missing

lint:
	flake8 src/ --max-line-length=100
	black --check src/

format:
	black src/
	isort src/

.PHONY: help install install-dev build-image push-image verify-env \
        generate-data compile-pipeline run-tests lint format
