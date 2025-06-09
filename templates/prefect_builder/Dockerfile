ARG BASE_IMAGE
FROM ${BASE_IMAGE}

ARG REG_NAME
ARG PREFECT_API_KEY
ARG PREFECT_API_URL
ARG SCRIPT_NAME
ARG TOML_CHANGE
ARG BASE_DIR_NAME=app

######################################## ADD CUSTOM COMMANDS #######################################
# RUN apt-get update && apt-get install curl -y
######################################## END CUSTOM COMMANDS #######################################

######################################## SETUP: DO NOT TOUCH ########################################
# Version of the current docker template being used
ENV TEMPLATE_VERSION="6.0"
ENV GOOGLE_APPLICATION_CREDENTIALS=/${BASE_DIR_NAME}/${SCRIPT_NAME}/cred.json
ENV PREFECT_API_KEY=${PREFECT_API_KEY}
ENV PREFECT_API_URL=${PREFECT_API_URL}

WORKDIR /temp
COPY . /temp
WORKDIR /${BASE_DIR_NAME}

RUN cp /temp/cred.json /temp/${SCRIPT_NAME} \
&& cp -r /temp/${SCRIPT_NAME} . \
&& python /temp/prefect_builder.py --reg-name ${REG_NAME} --script-name ${SCRIPT_NAME} --toml-change ${TOML_CHANGE}
######################################## SETUP: DO NOT TOUCH ########################################

######################################## CLEANUP: DO NOT TOUCH #####################################
RUN rm -rf /temp ${SCRIPT_NAME} .prefectignore /bin/uv /bin/uvx
# Will be injected at runtime
ENV PREFECT_API_KEY=""
ENV PREFECT_API_URL=""
######################################## CLEANUP: DO NOT TOUCH #####################################
