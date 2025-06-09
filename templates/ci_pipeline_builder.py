import base64
import json
import os
import tomllib
from ast import literal_eval
from pathlib import Path
from shlex import split as shlex_split
from subprocess import PIPE, run as sub_run

import boto3
import s3fs
from botocore.exceptions import ClientError
from google.cloud import secretmanager

##################### BUILD VARIABLES #####################

# Python docker image names
PYBASE_IMAGE_39 = "python_base_39:latest"
PYBASE_IMAGE_311 = "python_base_311:latest"
PYBASE_IMAGE_313 = "python_base_313:latest"

# Default Prefect workspace
DEFAULT_WORKSPACE = "prod"
# default cloud to use
DEFAULT_CLOUD = "aws"
# Default python version
DEFAULT_PYVER = "3.11"

# AWS settings
AWS_REGIONS = ["us-east-1", "eu-west-1"]
SAMA_AWS_ID = os.getenv("SAMA_AWS_ACC_ID")
NAR_AWS_ID = os.getenv("NAR_AWS_ACC_ID")
AWS_PUB_REG = "public.ecr.aws/j1p3q0y5"
AWS_PRI_REG = f"{NAR_AWS_ID}.dkr.ecr.us-east-1.amazonaws.com"
AWS_CF_REG = "narwhal-ecr"

# GCP settings
GCP_PROJECT_ID = os.getenv("GCP_PROJ")
GCP_PRI_REG = f"us-central1-docker.pkg.dev/{GCP_PROJECT_ID}/narwhal-docker"
# name of the SA key file used to access GCP resources by the CI pipeline
SA_SMAR_ENV = "SA_SMAR_KEY"
GCP_CF_REG = "narwhal-docker"

# Azure settings
AZ_CF_REG = "narwhalazure"
AZ_PRI_REG = "narwhalazure.azurecr.io"

# Name of shell script where all the build env variables are set
BASH_SCRIPT_NAME = "set_build_env.sh"

# Codefresh (CI pipeline) Settings
CODEFRESH_PATH = os.getenv("CF_VOLUME_PATH")
REPO_NAME = os.getenv("CF_REPO_NAME")
PREFECT_VER = os.getenv("PREFECT_VER", "2.x.x")

# ECR POLICIES
principal = f"arn:aws:iam::{SAMA_AWS_ID}:root"
ECR_PULL_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowCrossAccPull",
            "Effect": "Allow",
            "Principal": {"AWS": principal},
            "Action": ["ecr:BatchGetImage", "ecr:GetDownloadUrlForLayer"],
        }
    ],
}

ECR_LIFECYCLE_POLICY = {
    "rules": [
        {
            "rulePriority": 1,
            "description": "delete after 2",
            "selection": {"tagStatus": "any", "countType": "imageCountMoreThan", "countNumber": 2},
            "action": {"type": "expire"},
        }
    ]
}

###############################################################


def get_json_data(json_file_path):
    """
    The function takes a file path for a JSON file and returns the data in the file as a Python object.

    Args:
      json_file_path: The file path of a JSON
    file.
    """
    with open(json_file_path, "r") as data_file:
        return json.load(data_file)


def write_output_json(json_data, json_file_path):
    """
    This function writes JSON data to a specified file path.

    Args:
      json_data: The data that you want to write to a JSON file.
      json_file_path: The file path where the JSON data will be written to.
    """
    with open(json_file_path, "w") as data_file:
        json.dump(json_data, data_file)


def search_filepath(filepath_arr, search_term):
    """
    This function takes in an array of filepaths and a search term.
    returns the filepath that contains the search term.

    Args:
      filepath_arr: It is an array of filepaths.
      search_term: The search term that we want to find the array of filepaths.
    """
    name_arr = [name for name in filepath_arr.glob(search_term) if name.is_file()]
    if len(name_arr) == 1 and name_arr[0].exists():
        return name_arr[0]


def check_for_file(full_path, search_terms):
    for search_term in search_terms:
        if search_term.lower() in full_path.name.lower():
            return {"path": full_path.parent, "container_name": full_path.parent.name}


# Take the first file that is changed in the git commits
# Look for the keyword flows in the path
# We then want to remove the parents paths that do not include that keyword
# This will remove all unnecessary paths
def get_slice_num(git_filepath, step_name):
    for slice_num, filepath in enumerate(git_filepath.parents[::-1]):
        if step_name in str(filepath):
            return slice_num + 1
    raise Exception(f"{step_name} keyword not found in filepath!")


def get_toml(git_path_arr, py_toml, step_name):
    # git_path_arr contains all the files that have changed in the git commit
    for git_filepath in git_path_arr:
        # check if the pyproject.toml file exists in first filepath
        if toml_path := search_filepath(git_filepath, py_toml):
            return toml_path
        else:
            # If not then we need to search the parent paths
            # Remove unnecessary parent paths by getting the slice number
            slice_num = -(get_slice_num(git_filepath, step_name))
            for filepath in list(git_filepath.parents)[:slice_num]:
                if toml_path := search_filepath(filepath, py_toml):
                    return toml_path
    return None


def create_google_service_keyfile(cred_path: str):
    if google_token := os.getenv(SA_SMAR_ENV):
        token = literal_eval(base64.b64decode(google_token).decode("UTF-8"))
        write_output_json(token, cred_path)


def get_secret(secret_name: str):
    """
    This Python function retrieves a secret from Google Cloud Secret Manager.

    Args:
      secret_name (str): The name of the secret that you want to retrieve.

    Returns:
      the decoded data
    """
    secret_client = secretmanager.SecretManagerServiceClient()
    secret_path = secret_client.secret_version_path(GCP_PROJECT_ID, secret_name, "latest")
    secret_data = secret_client.access_secret_version(name=secret_path)
    return secret_data.payload.data.decode("UTF-8")


def set_prefect_api(workspace: str):
    # No longer have a test workspace
    if workspace == "test":
        print("WARNING: TEST WORKSPACE IS DEPRECATED USING PROD INSTEAD!")
    #     prefect_key = get_secret("PREFECT_API_KEY_TEST")
    #     prefect_url = get_secret("PREFECT_API_URL_TEST")
    # else:
    prefect_key = get_secret("PREFECT_API_KEY")
    prefect_url = get_secret("PREFECT_API_URL")
    return prefect_key, prefect_url


def select_registry(cloud: str):
    if cloud == "aws":
        return AWS_PRI_REG, AWS_CF_REG
    elif cloud == "gcp":
        return GCP_PRI_REG, GCP_CF_REG
    elif cloud == "azure":
        return AZ_PRI_REG, AZ_CF_REG


def create_aws_ecr_repo(script_name: str, aws_id: str, aws_key: str):
    for aws_region in AWS_REGIONS:
        try:
            client = boto3.client(
                "ecr", region_name=aws_region, aws_access_key_id=aws_id, aws_secret_access_key=aws_key
            )
            client.describe_repositories(repositoryNames=[script_name])
            print(f"ECR repo {script_name} already exists in {aws_region} skipping creation!")
        except ClientError as e:
            if e.response["Error"]["Code"] == "RepositoryNotFoundException":
                try:
                    print(f"Creating ECR repo for {script_name} in region {aws_region}")
                    client.create_repository(repositoryName=script_name)
                    print(f"Setting ECR policy for {script_name} in region {aws_region}")
                    client.set_repository_policy(repositoryName=script_name, policyText=json.dumps(ECR_PULL_POLICY))
                    print(f"Setting ECR lifecycle policy for {script_name} in region {aws_region}")
                    client.put_lifecycle_policy(
                        repositoryName=script_name, lifecyclePolicyText=json.dumps(ECR_LIFECYCLE_POLICY)
                    )
                except ClientError as e:
                    raise Exception(f"Failure: {script_name} in {aws_region} with error: {e.response['Error']}")


def main():
    ########## ENV VIRABLES ###########
    # Current git hash used to get list of git commits
    # Provided by CF
    hash_git = os.getenv("GIT_HASH")
    # Hard coded for the CF pipeline
    # Can be either container_images or flows
    step_name = os.getenv("STEP_NAME")
    flow_path = os.getenv("FLOW_PATH")
    ####################################

    print(f"THE NARWHAL CI IS RUNNING THE FOLLOWING PIPELINE/GITHASH: {step_name}/{hash_git}")

    home_path = Path(str(Path.cwd()).split(REPO_NAME, 1)[0]).joinpath(REPO_NAME)

    # Avoids having to add an empty arr check
    git_changes_arr = []

    # This is check if needed when the system enters maintenance mode
    # Maint mode does not need to grab a list of files that have changed during a git commit
    # Maint mode already knows where the files are located
    if "maint" not in step_name:
        command_str = f"git diff-tree --no-commit-id --name-only -r {hash_git}"
        git_results = sub_run(shlex_split(command_str), stdout=PIPE)

        git_changes_arr = list(git_results.stdout.decode("utf8").split())
        if not git_changes_arr:
            raise Exception("NO GIT DATA FOUND")
        git_path_arr = [home_path.joinpath(file_path) for file_path in git_changes_arr]

    # Pipewhal needs access to GCP
    # Create the google token
    create_google_service_keyfile(str(Path(CODEFRESH_PATH).joinpath("cred.json")))

    # Grab all required secrets from GCP
    aws_cred = literal_eval(get_secret("AWS_NARWHAL_PROD"))
    aws_id = aws_cred.get("id")
    aws_key = aws_cred.get("key")

    # RUN THE PIPELINE
    # Check with pipeline we are trying to run
    if step_name in ["container_images", "maint-ci"]:
        print("BUILDING CONTAINER IMAGES")
        if "maint" in step_name:
            git_path_arr = [home_path.joinpath(flow_path)]
            print(f"Grabbing the image data from: {str(git_path_arr[0])}")
        search_terms = ["Dockerfile", "build_settings.json"]
        file_arr = [check_for_file(full_path, search_terms) for full_path in git_path_arr]
        if not file_arr:
            raise FileNotFoundError("No files found when trying to build container images!")
        # Filter list of [dict, dict...] to exclude None
        # This will guarentee that you return the first valid dict value if it exists
        build_file_dict = list(filter(None, file_arr))[0]
        build_settings_file = search_filepath(build_file_dict.get("path"), search_terms[1])

        print("CREATING SHELL ENV FILE")
        with open(BASH_SCRIPT_NAME, "w") as build_file:
            build_file.write("#!/bin/bash\n")
            if not build_settings_file:
                raise FileNotFoundError("build_settings.json")

            build_json = get_json_data(build_settings_file)
            if build_image_name := build_json.get("image_name"):
                build_file.write(f"cf_export SAMA_BUILD_IMAGE={build_image_name}\n")
            if build_image_tag := build_json.get("tag"):
                if build_image_tag == "base":
                    build_file.write(f"cf_export SAMA_BUILD_TAG=prefect-{PREFECT_VER}\n")
                else:
                    build_file.write(f"cf_export SAMA_BUILD_TAG={build_image_tag}\n")
            if not (build_registry := build_json.get("registry")):
                raise Exception("Missing registry field!")

            # If test is set then we use the url and password for the test prefect server
            workspace = build_json.get("workspace", DEFAULT_WORKSPACE)
            prefect_key, prefect_url = set_prefect_api(workspace)

            build_file.write(f"echo PREFECT_KEY={prefect_key} >> {CODEFRESH_PATH}/env_vars_to_export\n")
            build_file.write(f"echo PREFECT_URL={prefect_url} >> {CODEFRESH_PATH}/env_vars_to_export\n")

            build_file.write(f"cf_export SAMA_BUILD_PROVIDER={build_registry}\n")
            build_file.write(f"cf_export SAMA_WORK_DIR={build_file_dict.get('path')}\n")
            container_image = build_file_dict.get("container_name")
            build_file.write(f"cf_export SAMA_IMAGE_NAME={container_image}\n")

        # TODO check if this is needed for the container images
        create_google_service_keyfile(f"{build_file_dict.get('path')}/cred.json")

        if build_registry == "aws" or build_registry == "all":
            create_aws_ecr_repo(container_image, aws_id, aws_key)

    elif step_name in ["flows", "maint-flows"]:
        py_toml = "pyproject.toml"

        if "maint" in step_name:
            fs = s3fs.S3FileSystem(anon=False, key=aws_id, secret=aws_key)
            print(f"Grabbing the flow data from cloud storage path: {flow_path}")
            local_path = Path(CODEFRESH_PATH).joinpath(f"flows/{Path(flow_path).stem}")
            fs.get(flow_path, str(local_path), recursive=True)
            git_path_arr = [local_path]

        if toml_path := get_toml(git_path_arr, py_toml, step_name):
            print(f"Toml file to process: {str(toml_path)}")
            root_flowpath = toml_path.parents[1]
        else:
            raise FileNotFoundError(py_toml)

        # Set defaults if sama-build is not set
        custom_image = False
        pyver = DEFAULT_PYVER
        workspace = DEFAULT_WORKSPACE
        cloud = DEFAULT_CLOUD

        with open(toml_path, "rb") as f:
            toml_data = tomllib.load(f)
            if sama_build := toml_data.get("sama-build"):
                custom_image = sama_build.get("custom-image", False)
                pyver = sama_build.get("pyver", DEFAULT_PYVER)
                workspace = sama_build.get("workspace", DEFAULT_WORKSPACE)
                cloud = sama_build.get("cloud", DEFAULT_CLOUD)

            toml_info = toml_data.get("project")
            # Modify name so that underscores are changed from "-" to "_"
            script_name = toml_info.get("name").replace("-", "_")
            script_version = toml_info.get("version") or "1.0.0"

        # python 3.11 is the default base image
        # TODO remove 3.9
        if pyver == "3.13":
            PYBASE = PYBASE_IMAGE_313
            base_ver = "pyver-3.13"
        elif pyver == "3.9":
            PYBASE = PYBASE_IMAGE_39
            base_ver = "pyver-3.9"
        else:
            PYBASE = PYBASE_IMAGE_311
            base_ver = "pyver-3.11"

        prefect_key, prefect_url = set_prefect_api(workspace)
        cloud_registry, cf_registry = select_registry(cloud)

        with open(BASH_SCRIPT_NAME, "w") as build_file:
            build_file.write("#!/bin/bash\n")
            build_file.write(f"echo PREFECT_KEY={prefect_key} >> {CODEFRESH_PATH}/env_vars_to_export\n")
            build_file.write(f"echo PREFECT_URL={prefect_url} >> {CODEFRESH_PATH}/env_vars_to_export\n")

            build_file.write(f"echo AWS_ID={aws_id} >> {CODEFRESH_PATH}/env_vars_to_export\n")
            build_file.write(f"echo AWS_KEY={aws_key} >> {CODEFRESH_PATH}/env_vars_to_export\n")

            build_file.write(f"cf_export SAMA_IMAGE_NAME={script_name}\n")
            build_file.write(f"cf_export SAMA_PYBASE={base_ver}\n")
            build_file.write(f"cf_export SAMA_WORK_DIR={root_flowpath}\n")
            build_file.write(f"echo WORKING_DIR={root_flowpath} >> work_dir.txt\n")
            build_file.write(f"cf_export SAMA_BUILD_TAG={script_version}\n")
            build_file.write(f"cf_export SAMA_TOML_LOC={str(toml_path)}\n")
            build_file.write(f"cf_export SAMA_PREFECT_VER=prefect-{PREFECT_VER}\n")
            build_file.write(f"cf_export SAMA_CF_REG={cf_registry}\n")

            build_file.write(f"cf_export SAMA_REG_NAME={cloud_registry}\n")
            build_file.write(f"cf_export SAMA_BASE_IMAGE={AWS_PRI_REG}/{PYBASE}\n")
            if custom_image:
                build_file.write(f"echo IMAGE_LOC={toml_path.parent} >> custom_image.txt\n")
            # Check if toml files exists in the git changes log
            # Set to true if maint mode is enabled
            if _ := [change for change in git_changes_arr if ".toml" in change] or "maint" in step_name:
                build_file.write(f"cf_export SAMA_TOML_CHANGE=yes\n")
            else:
                build_file.write(f"cf_export SAMA_TOML_CHANGE=no\n")

        # Needed so that the prefect builder stage of the pipeline
        # can access the GCP resources
        create_google_service_keyfile(f"{root_flowpath}/cred.json")
        create_aws_ecr_repo(script_name, aws_id, aws_key)


if __name__ == "__main__":
    main()
