import asyncio
import gzip

import aiofiles
import httpx
import litestar.status_codes as status
import msgspec
from config.gateway_settings import settings
from config.log import logger
from litestar.exceptions import HTTPException
from utils.multicloud import CloudStorage


def get_prefect_creds():
    # TODO uncomment only if you have a second test workspace
    # if settings.USE_TEST_WORKSPACE:
    #     return settings.PREFECT_TEST_URL, settings.PREFECT_TEST_KEY
    return settings.PREFECT_API_URL, settings.PREFECT_API_KEY


PREFECT_URL, PREFECT_API = get_prefect_creds()


def chunks(lst: list[str], n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def create_blob_path(
    project_id: str,
    task_id: str,
    blob_name: str | None = None,
    suffix: str = "gz",
    task_round: str | None = None,
) -> str:
    """
    It creates a blob path for a given project and task id, and optionally a blob name

    Args:
        project_id (str): The project ID of the project you want to download the data from.
        task_id (str): The task id of the task that you want to download the data for.
        blob_name (str): The name of the blob to be created.
        suffix (str): The file extension of the blob. Defaults to .gz (gzipped)

    Returns:
        A string that is the path to the blob.
    """
    # await async_sleep(0.1)
    path_name = (
        blob_name or f"{project_id}{settings.DELMITER}{task_id}{settings.DELMITER}{task_round}.{suffix}"
        if task_round
        else f"{project_id}{settings.DELMITER}{task_id}.{suffix}"
    )
    return f"{settings.DATA_STORE}/{path_name}"


async def store_task(
    project_id: str,
    task_id: str,
    task: dict,
    task_round: str = None,
    encoder: msgspec.json.Encoder = None,
    storage: CloudStorage = None,
) -> bool:
    """
    This function compresses the task data and caches the data in cloud storage.
    The task can then be queried at a later time.

    Args:
      project_id (str): SamaHub project id
      task_id (str): SamaHub task id
      task (dict): The task data to be stored
      task_round (str): Integer that specifies the round number for the task
    """
    r_path = create_blob_path(project_id=project_id, task_id=task_id, task_round=task_round)
    logger.info(f"STORING TASK AT LOCATION: {r_path}")
    # Setting the allow repeat flag to true enables overwriting a task that already exists
    # Doing this because the delivery format is still missing the round metadata
    try:
        data_to_compress = encoder.encode(task)
        gzipped_data = gzip.compress(data_to_compress)
        async with aiofiles.tempfile.NamedTemporaryFile(suffix=".gz") as temp:
            async with aiofiles.open(temp.name, "wb") as f:
                await f.write(gzipped_data)
            await storage.fs._put(temp.name, r_path)
        logger.info("STORED TASK SUCESSFULLY")
        return True
    except Exception as e:
        logger.error(f"FAILED TO STORE TASK: {e}")
        return False


def check_params(usr_params: dict):
    if dep_name := usr_params.get("dep_name"):
        del usr_params["dep_name"]
    # no_round disables adding round to the flow tag
    # only works on the dpp event source
    # webhooks do not support this feature
    if no_round := usr_params.get("no_round"):
        del usr_params["no_round"]
    workspace = usr_params.get("workspace")
    if workspace and workspace == "test":
        del usr_params["workspace"]
        settings.USE_TEST_WORKSPACE = True
    return usr_params, dep_name, no_round


async def get_work_pool() -> list | None:
    headers = {"Authorization": f"Bearer {PREFECT_API}"}
    endpoint = f"{PREFECT_URL}/work_pools/filter"
    pool_names = []
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(endpoint, headers=headers)
            response.raise_for_status()
            pool_names.extend((pool["name"], pool["type"]) for pool in response.json())
            return pool_names
        except Exception as e:
            logger.error(e)


async def create_flow_run(
    script_name: str,
    project_id: str,
    task_id: str,
    usr_params: dict,
    dep_name: str = None,
    task_round: int = None,
    dep_id: str = None,
) -> bool:
    """
    This function creates a new flow run on NPS-Prod (prefect)

    Args:
      script_name (str): The name of the flow
      project_id (str): The SamaHub project id
      task_id (str): The SamaHub task id
      usr_params (dict): A dictionary containing the input parameters for the script that will be executed in the flow run.      dep_name (str): dep_name is an optional parameter that represents the name of the dependency flow
      task_round (int): Optional integer that specifies the round number for task
      dep_id (str): The flow's deployment id
    """
    # make sure project id is a string
    project_id = str(project_id)
    deploy_name = dep_name or f"{script_name}_{settings.DEPLOYMENT_KEYWORD}"
    prefect_name = f"{script_name}/{deploy_name}"

    headers = {"Authorization": f"Bearer {PREFECT_API}"}

    async with httpx.AsyncClient() as client:
        try:
            endpoint = f"{PREFECT_URL}/deployments/name/{prefect_name}"
            response = await client.get(endpoint, headers=headers)
            error_resp = response.is_error
            logger.info(f"STATUS CODE: {response.status_code} IS_ERROR: {error_resp}")
            if error_resp:
                logger.error(f"COULD NOT FIND DEPLOYMENT USING SCRIPT NAME: {prefect_name}")
                return False

            dep_id = response.json().get("id")
            logger.info(f"DEPLOYMENT ID: {dep_id}")
            logger.info(f"FOUND DEPLOYMENT: {prefect_name}")

            data = {
                "parameters": usr_params,
                "name": task_id,
                "tags": [project_id, task_id, f"round {task_round}" if task_round else "round 0"],
            }
            endpoint = f"{PREFECT_URL}/deployments/{dep_id}/create_flow_run"
            response = await client.post(endpoint, headers=headers, json=data)
            if response.is_error:
                logger.error(f"FAILED TO CREATE FLOW RUN:  {response.status_code}--{response.json()}")
                return False
            return True

        except HTTPException as e:
            if e.status_code == status.HTTP_429_RETRY_AFTER:
                logger.info(f"Retrying flow run after sleeping for {settings.SLEEP_TIME} second(s)")
                asyncio.sleep(settings.SLEEP_TIME)
                await create_flow_run(
                    script_name=script_name,
                    project_id=project_id,
                    task_id=task_id,
                    usr_params=usr_params,
                    dep_name=deploy_name,
                    task_round=task_round or None,
                    dep_id=dep_id,
                )
            else:
                logger.error(e)
                return False
        except Exception as e:
            logger.error(e)
            return False
