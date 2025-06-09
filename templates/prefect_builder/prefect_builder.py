# import asyncio
import argparse
import importlib.metadata
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from shlex import split as shlex_split
from subprocess import DEVNULL, run as sub_call


def prefect_deps():
    # pyyaml and toml are bundled with Prefect
    # TODO: In the future yaml and toml should get installed separately
    try:
        # make this global in scope
        global yaml, CronSchedule, IntervalSchedule, RRuleSchedule, toml_load  # , get_client

        import yaml

        # from prefect.client.orchestration import get_client
        from prefect.server.schemas.schedules import CronSchedule, IntervalSchedule, RRuleSchedule
        from toml import load as toml_load
    except ImportError:
        raise ImportError("FAILED TO IMPORT PREFECT DEPENDENCIES!")


def parse_arguments():
    parser = argparse.ArgumentParser(description="Configuration arguments.")

    # Define the arguments
    parser.add_argument("--reg-name", type=str, help="Registration Name", required=True)
    parser.add_argument("--script-name", type=str, help="Script Name", required=True)
    parser.add_argument("--toml-change", type=str, help="TOML file change description", required=False)

    # Parse the arguments
    args = parser.parse_args()
    return args


##################### BUILD VARIABLES #####################

# misc settings
PREFECT_EXTRAS = "[aws]"
SUCCESS_CODE = 0
FAILURE_CODE = 1

# AWS ECS Fargate storage range is: 21Gi to 200Gi per pod
# GCP GKE Autopilot storage range is: 10Mi to 10Gi per pod
RESOURCE_LIMIT_MAP = {
    "very-low": {"cpu": "0.5", "memory": "512Mi"},
    "low": {"cpu": "1", "memory": "2Gi"},
    "med": {"cpu": "1", "memory": "4Gi"},
    "high": {"cpu": "2", "memory": "4Gi"},
}

# infra defaults
DEFAULT_INFRA_TYPE = "giver"
DEFAULT_NARWHAL_INFRA_TYPE = "ecs"
DEFAULT_ECS_VOLUME_SIZE = "21Gi"
DEFAULT_GKE_VOLUME_SIZE = "10Gi"

# config defaults
DEFAULT_REGION = "us"
DEFAULT_DEPLOY_NUM = 1
DOCKER_TEMPLATE_VERSION = "6.0"
DEFAULT_DEPLOY_LIST = []
DEFAULT_DEPLOY_JSON = False
DEFAULT_NPS_EXT = []
DEFAULT_RESOURCE_LIMIT = RESOURCE_LIMIT_MAP["low"]

# prefect settings
FLOW_CLOUD_STORAGE = "narwhal-flow-store"
QUEUE_PREFIX = "narq"

DEFAULT_PREFECT_TEMPLATE = {
    "name": "prefect_builder",
    "prefect-version": "",
    "build": None,
    "pull": [
        {
            "prefect_aws.deployments.steps.pull_from_s3": {
                "id": "pull_code",
                "bucket": "",
                "folder": "",
                "credentials": "{{ prefect.blocks.aws-credentials.aws-prefect-sa }}",
            }
        }
    ],
    "deployments": [],
}

###############################################################


def get_installed_version(package_name: str) -> str:
    """
    This function retrieves the installed version of a package.

    Args:
      package_name (str): The name of the package that you want to retrieve the version for.
    Returns:
      The function `get_installed_version` returns the version of the package that was installed.
    """
    try:
        return importlib.metadata.version(package_name)
    except importlib.metadata.PackageNotFoundError:
        return None


def run_command(command_str: str, no_output: bool = False) -> int:
    """
    This function runs a command and returns its exit code, with an option to suppress output.

    Args:
      command_str (str): A string representing the command to be executed.
      no_output (bool):  If set the output of the command will be redirected to the `DEVNULL` stream and not displayed.
    Returns:
      The return code of the command that was executed.
    """
    print(f"Running: {command_str}")
    if no_output:
        results = sub_call(shlex_split(command_str), stdout=DEVNULL)
    else:
        results = sub_call(shlex_split(command_str))
    return results.returncode


def ecs_resource_conversion(pod_cpu: str, pod_mem: str):
    ecs_temp_cpu = float(pod_cpu)
    if ecs_temp_cpu % 2 in [1, 1.0] and ecs_temp_cpu != 1.0:
        ecs_cpu = int((ecs_temp_cpu + 1) * 1024)
    else:
        ecs_cpu = int(ecs_temp_cpu * 1024)

    if "Mi" in pod_mem:
        # this is min value of memory accepted
        ecs_mem = "512"
    else:
        ecs_temp_mem = int(pod_mem.split("Gi")[0])
        if ecs_temp_mem % 2 != 0 and ecs_temp_mem != 1:
            ecs_temp_mem += 1
        ecs_mem = ecs_temp_mem * 1024
    return int(ecs_cpu), int(ecs_mem)


def set_infra(script_name, image_name, infra_type, resource_dict):

    cpu = resource_dict["cpu"]
    memory = resource_dict["memory"]
    disk_size = resource_dict.get("disk", None)

    if infra_type == "gke":
        k8_infra = {
            "cpu": int(cpu),
            "memory": memory,
            "image": image_name,
        }
        if disk_size:
            if "Gi" in disk_size:
                inputted_size = int(disk_size.split("Gi")[0])
                default_size = int(DEFAULT_GKE_VOLUME_SIZE.split("Gi")[0])
                if inputted_size <= default_size:
                    k8_infra["ephemeral_storage"] = inputted_size
                else:
                    print(
                        f"WARNING: GKE disk size must be less than or equal to {DEFAULT_GKE_VOLUME_SIZE}, setting size to 1Gi!"
                    )
        return k8_infra

    elif infra_type == "ecs":
        ecs_cpu, ecs_mem = ecs_resource_conversion(cpu, memory)
        # disk must be of type int for ecs (https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_EphemeralStorage.html)
        # disk size is of type string since Giver and K8 use string units (8Gi)
        disk = disk_size or DEFAULT_ECS_VOLUME_SIZE
        if "Gi" in disk:
            inputted_size = int(disk.split("Gi")[0])
            default_size = int(DEFAULT_ECS_VOLUME_SIZE.split("Gi")[0])
            if inputted_size >= default_size:
                disk = inputted_size
            else:
                print(
                    f"WARNING: ECS disk size must be greater than or equal to 21Gi, setting to default value of {DEFAULT_ECS_VOLUME_SIZE}"
                )
                disk = default_size
        else:
            raise ValueError(f"ERROR: Incorrect units used, disk size must be in Gi. The value entered was {disk}")

        return {
            "cpu": ecs_cpu,
            "memory": ecs_mem,
            "image": image_name,
            "family": script_name,
            "name": f"{script_name}_ecs_job",
            "ephemeral_storage": disk,
        }

    elif infra_type == "giver":
        giver_dsl = {
            "dsl": {
                "steps": [
                    {
                        "image": image_name,
                        "entrypoint": ["python", "-m", "prefect.engine"],
                        "parameters": [],
                        "limits": {"cpu": cpu, "memory": memory},
                    }
                ],
            }
        }
        if disk_size:
            giver_dsl["dsl"]["volume"] = {"size": disk_size}
        return giver_dsl


def generate_deployment_cli(
    script_name, script_version, dep_filepath, infra_type, region, deploy_dict, cloud, infra_config
):
    # In order to the Prefect agent to pick up flow runs from the server
    # we need to add static prefix to the queue name, this lets the agent know
    # that all flow runs in the prefixed queues must be picked up
    queue_name = f"{QUEUE_PREFIX}_{script_name}"

    # Set the work pool
    if infra_type == "giver":
        work_pool = "giver"
    elif infra_type == "gke":
        work_pool = f"narpool-gke-eu"
    elif cloud == "aws":
        work_pool = f"narpool-{cloud}-{region}"
    else:
        work_pool = f"narpool-{cloud}"

    # path to the prefect flow (main python script)
    package_path = Path(script_name).joinpath(f"{script_name}.py")
    flow_script_path = Path.cwd().joinpath(package_path)
    if not flow_script_path.exists():
        raise FileNotFoundError(
            f"Flow not found at {flow_script_path}! Please verify that you have named and stored the file correctly!"
        )

    # Set the push/pull folder location
    pull_step = DEFAULT_PREFECT_TEMPLATE["pull"][0]["prefect_aws.deployments.steps.pull_from_s3"]
    pull_step["bucket"] = FLOW_CLOUD_STORAGE
    pull_step["folder"] = script_name
    push_step = [
        {
            "prefect_aws.deployments.steps.push_to_s3": {
                "id": "push_code",
                "bucket": FLOW_CLOUD_STORAGE,
                "folder": script_name,
                "credentials": "{{ prefect.blocks.aws-credentials.aws-prefect-sa }}",
            }
        }
    ]

    # Unpack the all user deployment data
    deploy_name_arr = deploy_dict["name"]
    param_arr = deploy_dict["param"]
    schedule_arr = deploy_dict["schedule"]

    for deploy_count, (deploy_name, param, schedule) in enumerate(zip(deploy_name_arr, param_arr, schedule_arr), 1):
        # Giver has been updated to use a offical custom worker
        DEFAULT_PREFECT_TEMPLATE["deployments"].append(
            {
                "name": deploy_name,
                "version": script_version,
                "tags": [],
                "schedule": schedule,
                "flow_name": None,
                "description": None,
                "entrypoint": f"{package_path}:main",
                "parameters": {} if param is None else param,
                "work_pool": {"name": work_pool, "work_queue_name": queue_name, "job_variables": infra_config},
                "push": None if deploy_count != 1 else push_step,
            }
        )

    # Must convet dict to yaml and save to file
    # yaml.Dumper.ignore_aliases = lambda *args: True
    with open(dep_filepath, "w") as outfile:
        yaml.dump(DEFAULT_PREFECT_TEMPLATE, outfile)
    cmd_str = f"prefect deploy --prefect-file {dep_filepath} --all"
    if run_command(cmd_str) == FAILURE_CODE:
        raise Exception("PREFECT DEPLOYMENT FAILURE")
    return SUCCESS_CODE


def create_resource_dict(toml_metadata):
    # if the amount specifier is not found then return None
    resource_dict = None
    if limit_type := toml_metadata.get("amount"):
        if limit_type.lower() == "custom":
            memory = toml_metadata.get("memory", RESOURCE_LIMIT_MAP["low"]["memory"])
            cpu = toml_metadata.get("cpu", RESOURCE_LIMIT_MAP["low"]["cpu"])
            disk = toml_metadata.get("disk", None)
            resource_dict = {"memory": memory, "cpu": cpu, "disk": disk} if disk else {"memory": memory, "cpu": cpu}
        elif limit_type.lower() in RESOURCE_LIMIT_MAP:
            resource_dict = RESOURCE_LIMIT_MAP[limit_type.lower()]
            if disk := toml_metadata.get("disk", None):
                resource_dict["disk"] = disk
    return resource_dict


def docker_template_version():
    """
    Checks the template version of the NPS's flow Dockerfile
    """
    if os.getenv("TEMPLATE_VERSION") != DOCKER_TEMPLATE_VERSION:
        raise ValueError(f"Template version mismatch. Please update your template to version {DOCKER_TEMPLATE_VERSION}")


def get_build_metadata(toml_data):
    toml_metadata = toml_data.get("sama-build", {})

    infra = toml_metadata.get("infra", DEFAULT_INFRA_TYPE)
    infra_type = DEFAULT_NARWHAL_INFRA_TYPE if infra == "narwhal" else infra

    return {
        "infra_type": infra_type,
        "region": toml_metadata.get("region", DEFAULT_REGION),
        "resource_dict": create_resource_dict(toml_metadata) or DEFAULT_RESOURCE_LIMIT,
        "deploy_num": toml_metadata.get("deploy-num", DEFAULT_DEPLOY_NUM),
        "deploy_list": toml_metadata.get("deploy-list", DEFAULT_DEPLOY_LIST),
        "deploy_json": toml_metadata.get("deploy-json", DEFAULT_DEPLOY_JSON),
        "nps_ext": toml_metadata.get("nps-ext", DEFAULT_NPS_EXT),
    }


def get_cloud_metadata(registry):
    if "aws" in registry:
        return "aws"
    return "gcp" if "docker.pkg.dev" in registry else "azure"


def get_prefect_schedule(schedule):
    if "cron" in schedule:
        return CronSchedule(**schedule)
    elif "interval" in schedule:
        interval = timedelta(seconds=schedule["interval"])
        anchor_date = datetime.fromisoformat(schedule["anchor_date"])
        return IntervalSchedule(interval=interval, anchor_date=anchor_date, timezone=schedule["timezone"])
    else:
        return RRuleSchedule(**schedule)


def main():
    ################ ENV VARIABLES + ARGS ############################
    # toml_change = os.getenv("SAMA_TOML_CHANGE")
    args = parse_arguments()
    script_name = args.script_name
    container_registry = args.reg_name
    prefect_ver = os.getenv("PREFECT_VER")
    ########################################################################

    # display the prefect version info
    print(f"Prefect version: {prefect_ver}")

    # checks the template version
    docker_template_version()

    # get the script location
    script_dir = Path.cwd().joinpath(script_name)

    # Need to change directory to so that we are in the correct
    # folder location where the pyproject.toml is located
    os.chdir(script_dir)

    ###################### INSTALL PACKAGE DEPENDENCIES ######################

    # Add the latest version of prefect to the build
    command_str = f"uv add prefect{PREFECT_EXTRAS}=={prefect_ver}"
    if run_command(command_str) != SUCCESS_CODE:
        raise Exception("FAILED TO INSTALL PREFECT!")

    # import the prefect dependencies
    prefect_deps()

    # Try installing without the dev flag first
    # If that fails then install with the dev flag
    command_str = f"uv sync --no-dev"
    if run_command(command_str) != SUCCESS_CODE:
        raise Exception("FAILED TO INSTALL PACKAGES!")
    # Verify that libnar is installed
    if not get_installed_version("libnar"):
        raise ImportError("PLEASE INSTALL THE LIBNAR PACKAGE AND REBUILD.")

    ########################################################################

    # set the prefect version in deployment template
    DEFAULT_PREFECT_TEMPLATE["prefect-version"] = prefect_ver

    # load the pyproject.toml data in for the flow
    toml_data = toml_load("pyproject.toml")

    # TODO: script version also exists in ci_pipeline_builder
    toml_ver = toml_data.get("project").get("version", None)
    script_version = f"{toml_ver}-prefect-{prefect_ver}"

    # Get the resource data if it exists
    build_metadata_dict = get_build_metadata(toml_data)
    infra_type, region, resource_dict, deploy_num, deploy_list, deploy_json, nps_ext = build_metadata_dict.values()

    # The name of the image that will be deployed.
    # giver is currently located in eu-west-1
    # TODO Remove check if this ever changes
    if region == "eu" or infra_type == "giver":
        container_registry = container_registry.replace("us-east-1", "eu-west-1")
    image_name = f"{container_registry}/{script_name}"

    ############################## NPS_EXT #############################
    # NPS extras (nps_ext) are additional packages that need to be installed
    # includes things like slam, etc
    if "slam" in nps_ext:
        if not get_installed_version("slamus"):
            raise ImportError("PLEASE INSTALL THE SLAMUS PACKAGE AND REBUILD.")
        if run_command("uv run build-slam") != SUCCESS_CODE:
            raise Exception("FAILED TO COMPILE SLAM!")
    ####################################################################

    # The path to the deployment file
    dep_filepath = str(script_dir.joinpath(f"{script_name}_deployment.yaml"))

    # Set as 1 by default if no deployment configs are found
    deploy_len = 1
    deploy_dict = {}

    if deploy_json:
        deploy_config = script_dir.joinpath("deploy.json")
        if not deploy_config.exists():
            raise FileNotFoundError(f"deploy.json NOT FOUND AT {deploy_config}!")
        with open(deploy_config, "r") as f:
            deploy_obj = json.load(f)
            deploy_data = deploy_obj.get("deploy", None)
            if deploy_data is None:
                raise ValueError("Deploy JSON is not formatted correctly! It must contain the key 'deploy'!")

        # get the deployment name data
        deploy_name_arr = [deploy_item["name"] for deploy_item in deploy_data]
        deploy_dict["name"] = deploy_name_arr
        deploy_len = len(deploy_name_arr)

        # get the schedule data
        deploy_dict["schedule"] = [deploy_item.get("schedule", None) for deploy_item in deploy_data]

        # get the parameter data
        deploy_dict["param"] = [deploy_item.get("parameters", None) for deploy_item in deploy_data]

    elif deploy_list:
        deploy_len = len(deploy_list)
        deploy_dict["name"] = deploy_list
        deploy_dict["schedule"] = [None] * deploy_len
        deploy_dict["param"] = [None] * deploy_len
    else:
        deploy_len = DEFAULT_DEPLOY_NUM if deploy_num == 0 else deploy_num
        default_name = f"{script_name}_deploy"
        deploy_dict["name"] = (
            [default_name] if deploy_len == 1 else [f"{default_name}_{dnum}" for dnum in range(1, deploy_len + 1)]
        )
        deploy_dict["schedule"] = [None] * deploy_len
        deploy_dict["param"] = [None] * deploy_len

    print(f"The number of deployments to create is: {deploy_len}")
    print("The following deployment(s) will be created:")
    print("\n".join(f"{i}: {item}" for i, item in enumerate(deploy_dict["name"], 1)))

    if not all(data is None for data in deploy_dict["schedule"]):
        print("\nThe following schedule(s) will be used:")
        print("\n".join(f"{i}: {json.dumps(item, indent=4)}" for i, item in enumerate(deploy_dict["schedule"], 1)))

    if not all(data is None for data in deploy_dict["param"]):
        print("\nThe following parameter(s) will be used:")
        print("\n".join(f"{i}: {json.dumps(item, indent=4)}" for i, item in enumerate(deploy_dict["param"], 1)))

    # get the cloud provider
    cloud = get_cloud_metadata(container_registry)

    # create federation credentials so that gcp resource can be accessed
    cred_data = {
        "infra_type": infra_type if infra_type == "giver" else "narwhal",
        "cloud": cloud,
    }
    with open(script_dir.joinpath("cred.json"), "w") as outfile:
        json.dump(cred_data, outfile)

    # register infra block with prefect so that it knows where to run the flow on
    # on a toml change re-register the infra block
    # if toml_change == "yes":
    infra_config = set_infra(script_name, image_name, infra_type, resource_dict)

    # build, register and store the flow code and the deployment with Prefect server
    if (
        generate_deployment_cli(
            script_name,
            script_version,
            dep_filepath,
            infra_type,
            region,
            deploy_dict,
            cloud,
            infra_config,
        )
        != SUCCESS_CODE
    ):
        raise Exception("FAILED TO GENERATE DEPLOYMENT!")


if __name__ == "__main__":
    # if async is required
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    # main(loop)
    main()
