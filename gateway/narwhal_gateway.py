import os
from ast import literal_eval
from asyncio import gather as async_gather, sleep as async_sleep
from datetime import datetime
from enum import Enum
from typing import Annotated, ClassVar, Literal, Optional

import aiobotocore
import httpx
import jwt
import litestar.status_codes as status
import msgspec
from config.gateway_auth import basic_auth, check_bearer_token, check_webhook_token
from config.gateway_settings import settings
from config.log import JE, log_config, logger
from litestar import Litestar, Response, get, post, put
from litestar.di import Provide
from litestar.openapi import OpenAPIConfig, OpenAPIController
from litestar.openapi.plugins import ScalarRenderPlugin
from litestar.types import Guard
from utils import npsops
from utils.multicloud import AWSCredInfo, CloudStorage
from utils.tunnel import start_ngrok

sama_store, narwhal_store = None, None


########## REMOTE FS SETUP ##########
async def get_aws_cred(env_var: str):
    aws_cred = literal_eval(os.getenv(env_var, "{}"))
    return aws_cred.get("id", None), aws_cred.get("key", None)


async def setup_remote_storage(env_var: str):
    id, secret = await get_aws_cred(env_var)
    storage = CloudStorage(cloud_vendor=settings.VENDOR, fs_use_async=True, cred_info=AWSCredInfo(id=id, secret=secret))
    storage.set_fs()
    storage.fs_session = await storage.fs.set_session()
    return storage


async def start_remote_fs():
    global sama_store, narwhal_store
    sama_store, narwhal_store = await async_gather(
        setup_remote_storage("AWS_SAMA_PROD"), setup_remote_storage("AWS_NARWHAL_PROD")
    )


async def close_session():
    await sama_store.fs_session.close()
    await narwhal_store.fs_session.close()


########## REMOTE FS SETUP ##########


class MyOpenAPIController(OpenAPIController):
    path = "/api"
    guards: ClassVar[list[Guard]] = [basic_auth]
    render_plugins = [ScalarRenderPlugin()]


class WebhookSchema(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(min_length=1, pattern="^[a-z_][a-z0-9_-]*$")]
    parameters: Optional[dict]


class DPPTask(msgspec.Struct):
    name: str
    parameters: Optional[dict]
    task: dict


class SamaTask(msgspec.Struct):
    task: dict


class MaintMode(str, Enum):
    ci = "maint-ci"
    # flow = "maint-flows"


class PrefectStateName(str, Enum):
    FAILED = "FAILED"
    CRASHED = "CRASHED"
    LATE = "LATE"
    COMPLETED = "COMPLETED"
    PENDING = "PENDING"


async def delete_ecr_repo(flow_name: str) -> bool:
    aws_id, aws_secret = await get_aws_cred("AWS_NARWHAL_PROD")
    session = aiobotocore.session.get_session(aws_access_key_id=aws_id, aws_secret_access_key=aws_secret)
    try:
        async with session.create_client("ecr", region_name="us-east-1") as us_client:
            await us_client.delete_repository(repositoryName=flow_name, force=True)

        async with session.create_client("ecr", region_name="eu-west-1") as eu_client:
            await eu_client.delete_repository(repositoryName=flow_name, force=True)
    except Exception as e:
        logger.error(e)
        return e


@put("/create-token")
async def generate_jwt_token(data: WebhookSchema) -> str:
    return jwt.encode(msgspec.structs.asdict(data), settings.DPP_KEY, algorithm=settings.ALGORITHM)


@post("/dpp-event", guards=[check_bearer_token])
async def dpp_event(data: DPPTask) -> Response:
    """
    This endpoint is used to retrieve task data for the DPP event source

    data (DPPTask):  The task data from SamaHub
    """
    # no_round is used if you want to not add round data
    # webhooks do not provide round data
    dep_name, no_round = None, None
    script_name = data.name
    project_id, task_id, task_round = data.task.get("project_id"), data.task.get("id"), data.task.get("round")
    usr_params = {
        "round": task_round,
        "project_id": project_id,
        "task_id": task_id,
    }

    logger.info("DPP EVENT RECEIVED")
    logger.info(f"Script Name: {script_name} Project ID: {project_id} Task ID: {task_id} Round: {task_round}")

    # process parameter data if it exists
    if data.parameters:
        usr_params |= data.parameters
        usr_params, dep_name, no_round = npsops.check_params(usr_params)

    if await npsops.store_task(
        project_id=project_id,
        task_id=task_id,
        task=data.task,
        task_round=None if no_round else task_round,
        encoder=JE,
        storage=sama_store,
    ) and await npsops.create_flow_run(
        script_name=script_name,
        project_id=project_id,
        task_id=task_id,
        usr_params={"param": usr_params},
        task_round=task_round,
        dep_name=dep_name,
    ):
        logger.info("SENDING RESPONSE TO DPP ENDPOINT")
        return Response(status_code=status.HTTP_200_OK, content="{}")
    return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content="DPP EVENT FAILED")


@post("/webhook-event", dependencies={"token_data": Provide(check_webhook_token, sync_to_thread=False)})
async def webhook_event(data: SamaTask, token_data: dict) -> Response:
    """
    This endpoint is used to retrive task data for the webhook event source

    Args:
      data (SamaTask): The data parameter is of type SamaTask, represents a hub task
      token_data (str): JWT decrypted token will contain flow name and optional parameters
    """
    dep_name = None
    # grab the script name from the token data
    script_name = token_data.get("name")
    # Remove .py suffix if it is added to the name
    script_name = script_name.split(".py", 1)[0] if ".py" in script_name else script_name

    project_id, task_id = data.task.get("project_id"), data.task.get("id")
    logger.info("WEBHOOK EVENT RECEIVED")
    logger.info(f"Script Name: {script_name} Project ID: {project_id} Task ID: {task_id}")

    usr_params = {
        "project_id": project_id,
        "task_id": task_id,
    }

    if token_data.get("parameters"):
        usr_params |= token_data.get("parameters")
        # no_round is discarded because webhooks do not provide round data
        usr_params, dep_name, _ = npsops.check_params(usr_params)

    if await npsops.store_task(
        project_id=project_id,
        task_id=task_id,
        task=data.task,
        encoder=JE,
        storage=sama_store,
    ) and await npsops.create_flow_run(
        script_name=script_name,
        project_id=project_id,
        task_id=task_id,
        usr_params={"param": usr_params},
        dep_name=dep_name,
    ):
        return Response(status_code=status.HTTP_200_OK, content="WEBHOOK EVENT SUCCESS")
    return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content="WEBHOOK EVENT FAILED")


@get("maint/work-pool/")
async def maint_work_pool() -> list | None:
    """
    This function pauses all work pools
    """
    logger.info("GETTING ALL WORKPOOLS")
    return await npsops.get_work_pool()


# TODO update code
@get("/maint/{maint_mode: str}")
async def maint_mode(maint_mode: MaintMode) -> Response:
    """
    This function perferms maintance actions based on the selected maintenance mode.
    MaintMode.ci = Update the container images
    MaintMode.flow = Pause all work queues and update all flow images

    Args:
      maint_mode (MaintMode): The maintenance mode you wish to set.
    """
    logger.info(f"MAINTENANCE MODE: {maint_mode}")
    try:
        if maint_mode == MaintMode.ci:
            logger.info("UPDATING CONTAINER IMAGES")
            step_id = settings.CF_CI_ID
            trigger_name = "conatiner-images-trigger"
            root_folder = "container_images"
            doc_file = "Dockerfile"
            flow_list = [
                f"{root_folder}/python_base_39/{doc_file}",
                f"{root_folder}/python_base_311/{doc_file}",
                f"{root_folder}/python_base_313/{doc_file}",
                f"{root_folder}/ecs_agent/{doc_file}",
            ]
        elif maint_mode == MaintMode.flow:
            step_id = settings.CF_FLOW_ID
            trigger_name = "flow-trigger"
            flow_files = await narwhal_store.fs._ls(settings.FLOW_PATH)
            flow_list = [f"s3://{flow}" for flow in flow_files]

        headers = {
            "Authorization": f"{settings.CF_TOKEN}",
            "Content-Type": "application/json; charset=utf-8",
        }
        async with httpx.AsyncClient() as client:
            logger.info("GETTING LIST OF ACTIVE FLOW RUNS")
            for flow in flow_list:
                payload = {
                    "branch": "main",
                    "trigger": trigger_name,
                    "variables": {"FLOW_PATH": flow, "CI_STEP_NAME": maint_mode},
                    "options": {},
                }
                response = await client.post(
                    f"https://g.codefresh.io/api/pipelines/run/{step_id}",
                    headers=headers,
                    data=JE.encode(payload),
                )
                logger.info(f"The command returned a value of: {response.status_code}")
            return Response(status_code=status.HTTP_200_OK, content="OK")
    except Exception as e:
        logger.error(e)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@get("/list-flow")
async def list_flow(limit: Annotated[int, msgspec.Meta(gt=0, le=200)] = 200, offset: int = 0) -> list[str] | Response:
    prefect_url, prefect_api = npsops.get_prefect_creds()
    headers = {"Authorization": f"Bearer {prefect_api}"}
    endpoint = f"{prefect_url}/flows/filter"
    print(limit, offset)
    if offset != 0 and offset % limit != 0:
        return Response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=f"offset must be a multiple of Limit: {limit}"
        )
    payload = {"offset": offset, "limit": limit}
    async with httpx.AsyncClient() as client:
        response = await client.post(endpoint, headers=headers, json=payload)
        if response.is_error:
            logger.error(f"flow-list (httpx post) - status_code: {response.status_code} message: {response.json()}")
            return Response(status_code=status.HTTP_404_NOT_FOUND, content=response.json())
        return [flow["name"] for flow in response.json()]


@get("/delete-flow-data/{flow_name: str}")
async def delete_flow_data(flow_name: str) -> Response:
    err_list = []
    err_map = {
        0: "FLOW_DELETE_ERROR",
        1: "DEPLOYMENT_DELETE_ERROR",
        2: "NO_DEPLOYMENTS_FOUND_ERROR",
        3: "INFRA_BLOCK_DELETE_ERROR",
        4: "NO_INFRA_BLOCK_FOUND_ERROR",
        5: "REPOSITORY_DELETE_ERROR",
        6: "S3_DATA_NOT_FOUND_ERROR",
        7: "S3_DELETE_ERROR",
    }

    prefect_url, prefect_api = npsops.get_prefect_creds()
    headers = {"Authorization": f"Bearer {prefect_api}"}

    async with httpx.AsyncClient() as client:
        logger.info(f"Deleting {flow_name} ...")

        endpoint = f"{prefect_url}/flows/name/{flow_name}"
        response = await client.get(endpoint, headers=headers)
        flow_id = response.json().get("id")
        if not (flow_id):
            logger.error("NO FLOW FOUND")
            return Response(status_code=status.HTTP_404_NOT_FOUND, content="NO FLOW FOUND")

        endpoint = f"{prefect_url}/flows/{flow_id}"
        response = await client.delete(endpoint, headers=headers)
        if response.is_error:
            err_list.append({err_map[0]: flow_name})

        endpoint = f"{prefect_url}/deployments/filter"
        payload = {"flows": {"id": {"any_": [flow_id]}}}
        response = await client.post(endpoint, headers=headers, json=payload)
        deployments = response.json()
        infra_id_arr = []
        if deployments and not response.is_error:
            for deployment in deployments:
                logger.info(f"Deleting {deployment['name']} ...")
                endpoint = f"{prefect_url}/deployments/{deployment['id']}"
                response = await client.delete(endpoint, headers=headers)
                if response.is_error:
                    err_list.append({err_map[1]: deployment["name"]})
                else:
                    infra_id_arr.append(deployment["infrastructure_document_id"])
        else:
            err_list.append({err_map[2]: flow_name})

        # Delete blocks
        if infra_id_arr:
            for infra_id in infra_id_arr:
                logger.info(f"Deleting {infra_id} ...")
                endpoint = f"{prefect_url}/block_documents/{infra_id}"
                response = await client.delete(endpoint, headers=headers)
                if response.is_error:
                    err_list.append({err_map[3]: infra_id})
        else:
            err_list.append({err_map[4]: flow_name})

        if msg := await delete_ecr_repo(flow_name):
            err_list.append({err_map[5]: msg})

        # Delete the flow from S3
        flow_loc = f"{settings.FLOW_PATH}{flow_name}"
        try:
            if await narwhal_store.fs._exists(flow_loc):
                # logger.info(f"Deleting {flow_name} from S3 ...")
                await narwhal_store.fs._rm(flow_loc, recursive=True)
                # logger.info(f"Deletion of {flow_name} from S3 complete!")
            else:
                err_list.append({err_map[6]: flow_name})
        except Exception as _:
            err_list.append({err_map[7]: flow_name})

    if err_list:
        logger.error(err_list)
        return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=err_list)
    return Response(status_code=status.HTTP_200_OK, content=f"{flow_name} DELETED SUCCESSFULLY")


@get("/deploy-json")
async def deploy_json(
    flow_name: str,
    deployment_name: Optional[str],
    offset: int = 0,
    limit: Annotated[int, msgspec.Meta(gt=0, le=200)] = 200,
) -> dict:
    prefect_url, prefect_api = npsops.get_prefect_creds()
    endpoint = (
        f"{prefect_url}/deployments/name/{flow_name}/{deployment_name}"
        if deployment_name
        else f"{prefect_url}/deployments/filter"
    )
    if offset != 0 and offset % limit != 0:
        return Response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=f"offset must be a multiple of Limit: {limit}"
        )
    payload = {"flows": {"name": {"any_": [flow_name.strip()]}}}
    payload["offset"] = offset
    payload["limit"] = limit
    headers = {"Authorization": f"Bearer {prefect_api}"}
    deploy_dict = {"deploy": []}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            logger.info(f"Response: {response.status_code}")
            json_data = response.json()
            if isinstance(json_data, dict):
                json_data = [json_data]
            for data in json_data:
                deploy_dict["deploy"].append(
                    {"name": data.get("name"), "schedule": data.get("schedule"), "parameters": data.get("parameters")}
                )
            if not deploy_dict["deploy"]:
                msg = f"flow_name: {flow_name} \ndeployment: {deployment_name}"
                return Response(status_code=status.HTTP_404_NOT_FOUND, content=msg)
            return deploy_dict
        except Exception as e:
            logger.error(e)
            if response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
                return Response(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=response.json())
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=str(e))


@get("/flow-run-id")
async def flow_run_id(
    flow_name: str,
    flow_run_name_arr: Optional[list[str]],
    deployment_name: Optional[str],
    flow_state: Optional[list[PrefectStateName]],
    start_time: Optional[list[str]],
    start_time_specifier: Optional[Literal["after_", "before_"]],
    offset: int = 0,
    limit: Annotated[int, msgspec.Meta(gt=0, le=200)] = 200,
) -> list[str]:
    prefect_url, prefect_api = npsops.get_prefect_creds()
    endpoint = f"{prefect_url}/flow_runs/filter-minimal"
    headers = {"Authorization": f"Bearer {prefect_api}"}
    payload = {"flows": {"type": {"any_": [flow_name.strip()]}}}
    if flow_state:
        payload["flow_runs"] = {"state": {"type": {"any_": flow_state}}}
    if flow_run_name_arr:
        payload["flow_runs"] = {"name": {"any_": flow_run_name_arr}}
    if start_time:
        try:
            dt = datetime.strptime(start_time, "%Y/%m/%d %I:%M:%S %p").strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError:
            return Response(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content=f"Invalid date format: {start_time}. Use the format: %Y/%m/%d %I:%M:%S %p Example: 2021/12/31 12:00:00 PM",
            )
        payload["flow_runs"]["expected_start_time"] = {start_time_specifier: dt}
    if offset != 0 and offset % limit != 0:
        return Response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=f"offset must be a multiple of Limit: {limit}"
        )
    payload["offset"] = offset
    payload["limit"] = limit
    if deployment_name:
        payload["deployments"] = {"name": {"any_": [deployment_name]}}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint, headers=headers, json=payload)
            response.raise_for_status()
            return [flow_run["id"] for flow_run in response.json()]
        except Exception as e:
            logger.error(response.json())
            logger.info(response.status_code)
            if response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY:
                return Response(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=response.json())
            return Response(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content=str(e))


@post("/modify-flow-run")
async def modify_flow_run(
    data: list[str],
    mode: Literal["retry", "delete"],
    rate_limit: Annotated[int, msgspec.Meta(gt=0, le=500)] = 200,
    retries: Annotated[int, msgspec.Meta(gt=0, le=10)] = 3,
    retry_sleep_sec: Annotated[int, msgspec.Meta(ge=30, le=60)] = 30,
) -> Response:
    prefect_url, prefect_api = npsops.get_prefect_creds()
    headers = {"Authorization": f"Bearer {prefect_api}"}
    error_arr = []
    transport = httpx.AsyncHTTPTransport(retries=retries)

    if not rate_limit and len(data) > 200:
        return Response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=f"rate_limit must be set if number of flow runs is greater than 200: {len(data)}",
        )

    for loop_count, rate_limit_id_arr in enumerate(npsops.chunks(data, rate_limit)):
        if loop_count != 0:
            logger.info(f"Sleeping for {retry_sleep_sec} seconds")
            await async_sleep(retry_sleep_sec)
        for flow_run_id in rate_limit_id_arr:
            if mode == "delete":
                endpoint = f"{prefect_url}/flow_runs/{flow_run_id}"
            else:
                endpoint = f"{prefect_url}/flow_runs/{flow_run_id}/set_state"
                payload = {"state": {"type": "SCHEDULED", "name": "AwaitingRetry"}}
            async with httpx.AsyncClient(transport=transport) as client:
                try:
                    response = (
                        await client.delete(endpoint, headers=headers)
                        if mode == "delete"
                        else await client.post(endpoint, headers=headers, json=payload)
                    )
                    response.raise_for_status()
                except Exception as e:
                    # For some reason Prefect delete api doesn't return response after successful deletion
                    # Causes httpx to raise the following error
                    if e == "Expecting value: line 1 column 1 (char 0)" and mode == "delete":
                        continue
                    logger.error(e)
                    error_arr.append(flow_run_id)
    if error_arr:
        return Response(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=error_arr)
    return Response(status_code=status.HTTP_200_OK, content=f"All operations using {mode} mode completed successfully!")


app = Litestar(
    [
        generate_jwt_token,
        maint_mode,
        webhook_event,
        dpp_event,
        list_flow,
        deploy_json,
        flow_run_id,
        modify_flow_run,
        # maint_work_pool,
    ],
    logging_config=log_config,
    openapi_config=OpenAPIConfig(
        title="Narwhal Gateway",
        version="4.0.0",
        openapi_controller=MyOpenAPIController,
    ),
    on_startup=[start_remote_fs, start_ngrok],
    on_shutdown=[close_session],
)
