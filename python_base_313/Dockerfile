# See build_settings.json for BUILD_IMAGE name
ARG BUILD_IMAGE
ARG UV_VER

# Dynamically pull the UV image using the ARG version
FROM ghcr.io/astral-sh/uv:${UV_VER} AS uv_stage

# Use the base image
FROM ${BUILD_IMAGE}

ARG PREFECT_VER
ARG GCP_PROJ

# Copy the files from the uv_stage
COPY --from=uv_stage /uv /uvx /bin/

# Set the environment variables
ENV PYTHONUNBUFFERED=True
ENV PREFECT_VER=${PREFECT_VER}
# compile python bytecode
ENV UV_COMPILE_BYTECODE=1
# Use system python
ENV UV_SYSTEM_PYTHON=true
# Use the local env
ENV UV_PROJECT_ENVIRONMENT="/usr/local/"

# Install google keyring
RUN uv pip install --index-url https://pypi.org/simple/ keyrings.google-artifactregistry-auth

# Google private package index
## UV Settings
ENV UV_KEYRING_PROVIDER=subprocess
# add private pypi repo
ENV UV_EXTRA_INDEX_URL=https://oauth2accesstoken@us-central1-python.pkg.dev/${GCP_PROJ}/narwhal-pypi/simple/
