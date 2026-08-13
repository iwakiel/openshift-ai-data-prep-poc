FROM quay.io/modh/runtime-images:runtime-datascience-ubi9-python-3.9-20241111-3f76685

WORKDIR /app

# Install system dependencies
USER root
RUN dnf install -y git && dnf clean all

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy and install the src package so pipeline components can import from it
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir -e .

USER 1000

LABEL maintainer="mlops-team" \
      description="Retail banking data preparation pipeline runtime image" \
      version="0.1.0"
