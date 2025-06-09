# Dockerfile is used as base template and builder for all other dockerfiles
# Used to set the python version and poetry version for all other images
# See build_settings.json for BUILD_IMAGE name

ARG BUILD_IMAGE
FROM $BUILD_IMAGE

ARG PREFECT_VER
ARG PREFECT_PACK=[aws]

RUN pip install --upgrade pip \
&& pip install prefect${PREFECT_PACK}==${PREFECT_VER}
