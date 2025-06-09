# -----------------------------------------------------------------------------
# CONNECTOR LIBRARY FOR THE NARWHAL PROCESSING SYSTEM (NPS)
# -----------------------------------------------------------------------------

import gzip
import os
import time
import urllib
import warnings
from ast import literal_eval
from dataclasses import dataclass
from datetime import datetime
from json import dumps
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Optional, Tuple, Union

import boto3
import httpx
import msgspec
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from dateutil import parser
from dateutil.tz import tzutc
from fsspec import AbstractFileSystem
from google.cloud import secretmanager
from google.oauth2.credentials import Credentials as gcp_credentials
from slack_sdk import WebClient

try:
    import libnar.multicloud as mc
except ImportError:
    import multicloud as mc
try:
    from azure.core.credentials import AccessToken, TokenCredential
    from azure.identity import ClientAssertionCredential

    # Must convert AccessToken to TokenCredential for adlfs
    # https://learn.microsoft.com/en-us/python/api/azure-storage-blob/azure.storage.blob.aio.blobserviceclient?view=azure-python#parameters
    # See credential parameter in the above url
    @dataclass
    class AZTokenCredential(TokenCredential):
        access_token: AccessToken

        def get_token(self, *scopes, **kwargs):
            return self.access_token

except ImportError:
    pass

# Cloud settings
GCP_PROJECT_ID = "solution-eng-345114"
AWS_EU_REGION = "eu-west-1"
AWS_US_REGION = "us-east-1"

# NPS settings
DATA_STORE = "sama-narwhal-data-store"
DELMITER = "--"
DEFAULT_CLOUD_VENDOR = "aws"

# default start path for running flow
BASE_PATH = "/app"
# default path for the block storage on giver
GIVER_BLOCK_STORAGE_PATH = "/workdir"

# SA Acccounts + Multicloud attributes
SAMA_EXT_SA = "sama-external@rd-prod-398911.iam.gserviceaccount.com"
NARWHAL_SA = "narwhal-sa-smar@solution-eng-345114.iam.gserviceaccount.com"
SAMA_EXT_AUDIENCE = "//iam.googleapis.com/projects/459623805419/locations/global/workloadIdentityPools/sama-external/providers/sama-external"
AZ_TARGET_SCOPES = ["https://storage.azure.com/.default"]

# For better performance only initialize once
JE = msgspec.json.Encoder()
JD = msgspec.json.Decoder()


class DPPTask(msgspec.Struct):
    round: int
    data: dict
    answers: dict


class DBInfo(msgspec.Struct):
    user: str
    dbname: str
    driver: str
    region: str
    type: str = "postgresql"
    port: str = "5432"
    endpoint: Optional[str] = None


class SlackUploads(msgspec.Struct):
    filepath: Optional[Union[list[str], str]]

    def __post_init__(self):
        self.filepath = [self.filepath] if isinstance(self.filepath, str) else self.filepath
        if self.filepath:
            non_existent_files = [file for file in self.filepath if not Path(file).exists()]
            if non_existent_files:
                raise FileNotFoundError(f"The following file(s) were not found: {', '.join(non_existent_files)}")


@dataclass
class BearerAuth(httpx.Auth):
    """
    HTTPX bearer token authentication.

    Args:
        token (str): The bearer token to use for authentication.
    """

    token: str

    def auth_flow(self, request):
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request


@dataclass
class FSProxy:
    # Generic proxy class to apply a custom method everytime
    # a functionfrom the fsspec is called
    # example: narcon.fs.ls would then call
    # before that method executes it this function triggers a custom method
    # typically used to check/refresh an expired oauth token
    fs_instance: Any
    pre_method: Any

    def __getattr__(self, name):
        attr = getattr(self.fs_instance, name)
        if callable(attr):

            def wrapper(*args, **kwargs):
                self.pre_method()
                return attr(*args, **kwargs)

            return wrapper
        return attr


@dataclass
class Narcon:
    cloud_vendor: str = DEFAULT_CLOUD_VENDOR
    project_id: Optional[str] = None
    task_id: Optional[str] = None
    cs: Optional[mc.CloudStorage] = None
    fs: Optional[AbstractFileSystem] = None
    infra_type: Optional[str] = None
    slack_client: Optional[WebClient] = None
    cred_info: Optional[mc.GCPCredInfo] = None
    debug: Optional[bool] = False

    def __post_init__(self):
        warnings.simplefilter("always", DeprecationWarning)
        self.nar_setup()

    def nar_setup(self):
        # infra_type will always be provided in the prod environment
        # Example file contents:
        # {
        #     "infra_type": "narwhal" --> narwhal or giver
        #     "cloud": "aws" --> aws, gcp, azure
        # }
        setup_path = self.create_path().joinpath("cred.json")
        if Path(setup_path).exists() and self.cred_info is None:
            meta = self.read_json(setup_path)
            if (infra_type := meta.get("infra_type")) and (cv := meta.get("cloud")):
                self.infra_type = infra_type
                gcp_audience = f"//iam.googleapis.com/projects/1024378210460/locations/global/workloadIdentityPools/nps-pool/providers/{self.infra_type}-{cv}"
                self.cred_info = mc.GCPCredInfo(audience=gcp_audience, refresh_mode="internal")
                self.generate_access_token(self.cred_info)
            else:
                raise Exception("INFRA_TYPE OR CLOUD NOT FOUND IN SETUP FILE!")

    def refresh_token_if_expired(self, cred_info: mc.CredInfo, cloud_vendor: str):
        if cloud_vendor == "gcp":
            # If the token is expired will generate a new token
            # https://cloud.google.com/iam/docs/reference/credentials/rest/v1/projects.serviceAccounts/generateAccessToken
            expiry_time = parser.isoparse(cred_info.token_expiry)
            if expiry_time.tzinfo != tzutc():
                raise ValueError("GCP TOKEN EXPIRY MUST BE IN UTC FORMAT!")
            if expiry_time <= datetime.now(tzutc()):
                self.generate_access_token(cred_info)
        elif cloud_vendor == "azure":
            expiry_time = cred_info.credential.access_token.expires_on
            current_time = int(time.time())
            if expiry_time <= current_time:
                az_token = ClientAssertionCredential(
                    tenant_id=cred_info.tenant_id, client_id=cred_info.client_id, func=self.get_cognito_token
                ).get_token(*AZ_TARGET_SCOPES)
                cred_info.credential = AZTokenCredential(az_token)

    def rt_validate(self, struct: msgspec.Struct, struct_type: any = None) -> msgspec.Struct:
        # By default msgspec will not validate data at runtime
        # To run validation need to encode/decode data first
        struct_type = struct_type or type(struct)
        return msgspec.json.decode(JE.encode(struct), type=struct_type)

    def set_slack_client(self):
        """
        This function sets up the slack client
        """
        self.slack_client = WebClient(token=self.get_secret("SLACK_OAUTH_TOKEN"))

    def notify_slack_channel(
        self,
        channel: str,
        msg_body: Union[list, str],
        title: str = "Narwhal Message",
        uploads: Optional[Union[list[str], str]] = None,
    ):
        if self.slack_client is None:
            self.set_slack_client()

        channel_id = None
        slack_uploads = self.rt_validate(SlackUploads(filepath=uploads)).filepath
        text = msg_body if isinstance(msg_body, str) else "Slack BlockKit Message"
        blocks = msg_body if isinstance(msg_body, list) else None

        try:
            response = self.slack_client.chat_postMessage(
                channel=channel,
                blocks=blocks,
                text=text,
                title=title,
            )
            channel_id = response.get("channel")

            if slack_uploads and channel_id:
                upload_data = [{"file": file, "title": Path(file).name} for file in slack_uploads]
                response = self.slack_client.files_upload_v2(channel=channel_id, title=title, file_uploads=upload_data)
            return True
        except Exception as e:
            return e

    def write_json(self, data: dict, filepath: Union[str, Path]):
        """
        This function takes a dictionary and writes it to a json file

        Args:
          data (dict): The data to be written to the json file.
          filepath (Union[str, Path]): The filepath where the file will be written.
        """
        with open(filepath, "wb") as f:
            f.write(JE.encode(data))

    def read_json(self, filepath: Union[str, Path], struct_type: Optional[msgspec.Struct] = None) -> dict:
        """
        This function takes a filepath to a json file and returns the data in the file as a dictionary

        Args:
          filepath (Union[str, Path]): The filepath to the json file.

        Returns:
          A dictionary containing the data in the json file.
        """
        if not Path(filepath).exists:
            raise FileNotFoundError(filepath)
        with open(filepath, "rb") as f:
            data = f.read()
            return msgspec.json.decode(data, type=struct_type) if struct_type else JD.decode(data)

    def db_connect(self, connector: Optional[Any] = None):
        """
        Setup connection to the Narwhal's internal database
        """
        try:
            import sqlalchemy
        except ModuleNotFoundError:
            raise ModuleNotFoundError("Missing the sqlalchemy package!")

        db_data = (
            literal_eval(self.get_secret("DB_INFO_AWS"))
            if self.cloud_vendor == "aws"
            else literal_eval(self.get_secret("DB_INFO_GCP"))
        )
        if db_pass := db_data.get("pass"):
            del db_data["pass"]

        db_info = self.rt_validate(struct=db_data, struct_type=DBInfo)

        # TODO Remove GCP connector at some point
        # def get_conn():
        #     conn_name = f"{GCP_PROJECT_ID}:{db_info.region}:{db_info.dbname}"
        #     return connector.connect(conn_name, db_info.driver, user=db_info.user, password=db_pass, db=db_info.dbname)

        # if self.cloud_vendor == "gcp":
        #     return sqlalchemy.create_engine(f"{db_info.type}+{db_info.driver}://", creator=get_conn)

        return sqlalchemy.create_engine(
            sqlalchemy.URL.create(
                f"{db_info.type}+{db_info.driver}",
                username=db_info.user,
                password=db_pass,
                host=db_info.endpoint,
                port=db_info.port,
                database=db_info.dbname,
            )
        )

    def get_aws_cred_session(self, aws_cred: Optional[dict]):
        # Creates a boto3 session
        # Can either supply the id, key and session token or
        # retrieve it from the environment
        if aws_cred:
            session = (
                boto3.Session(
                    aws_access_key_id=aws_cred["AccessKeyId"],
                    aws_secret_access_key=aws_cred["SecretKey"],
                    aws_session_token=aws_cred["SessionToken"],
                )
                .get_credentials()
                .get_frozen_credentials()
            )
        else:
            session = boto3.Session().get_credentials().get_frozen_credentials()
        return session

    def generate_access_token(self, cred_info: mc.GCPCredInfo):
        if cred_info.refresh_mode == "internal":
            subject_token = self.get_aws_caller_identity(audience=cred_info.audience)
            sts_token = self.get_gcp_sts_token(audience=cred_info.audience, subject_token=subject_token)
            token_info = self.gcp_impersonate_token(sa_email=NARWHAL_SA, gcp_token=sts_token)
        elif cred_info.refresh_mode == "external":
            subject_token = self.get_aws_caller_identity(
                audience=SAMA_EXT_AUDIENCE, aws_cred=self.get_cognito_token(open_id=False)
            )
            sts_token = self.get_gcp_sts_token(audience=SAMA_EXT_AUDIENCE, subject_token=subject_token)
            if cred_info.sa_email is None:
                raise Exception("SA EMAIL NOT SET")
            ext_token = self.gcp_impersonate_token(sa_email=SAMA_EXT_SA, gcp_token=sts_token)["accessToken"]
            token_info = self.gcp_impersonate_token(sa_email=cred_info.sa_email, gcp_token=ext_token)
        else:
            return None
        cred_info.token = token_info["accessToken"]
        cred_info.token_expiry = token_info["expireTime"]

    def get_sama_acc_info(self, client_id: str, cloud_vendor: str = None):
        # Internal Sama Account API
        # Used to retrive client specific metadata for multicloud storage
        acc_url = self.get_secret("ACCOUNTS_BASE_URL")
        acc_key = self.get_secret("ACCOUNTS_API_KEY")
        headers = {"Accept": "application/json", "X-API-Key": f"{acc_key}"}
        url = f"{acc_url}/api/clients/{client_id}/cloud-providers/info"

        try:
            response = httpx.get(url, headers=headers)
            response.raise_for_status()
            if acc_info_arr := response.json().get("data"):
                for acc_info in acc_info_arr:
                    if acc_info.get("type") == cloud_vendor == "azure":
                        cid = acc_info.get("cloudProviderClientId")
                        tid = acc_info.get("cloudProviderTenantId")
                        account_name = acc_info.get("prefix")
                        return cid, tid, account_name
                    elif acc_info.get("type") == cloud_vendor == "gcp":
                        return acc_info.get("serviceAccountEmail")
            raise Exception("SAMA ACCOUNT INFO IS EMPTY!")
        except Exception as e:
            raise Exception(f"COULD NOT RETRIEVE SAMA ACCOUNT INFO! {e}")

    def get_cognito_token(self, open_id: bool = True):
        # This allows the infra to assume to the sama-cloud-connector-role-prod role
        # Needed when utilizing Sama's multicloud storage solution
        pool_id = self.get_secret("AWS_COGNITO_POOL_ID")
        logins = literal_eval(self.get_secret("AWS_COGNITO_LOGINS"))

        client = boto3.client("cognito-identity", region_name=AWS_EU_REGION)
        try:
            token_resp = client.get_open_id_token_for_developer_identity(IdentityPoolId=pool_id, Logins=logins)
            open_id_token = token_resp.get("Token")
            if open_id:
                return open_id_token
            return client.get_credentials_for_identity(
                IdentityId=token_resp.get("IdentityId"),
                Logins={"cognito-identity.amazonaws.com": open_id_token},
            ).get("Credentials")
        except Exception as e:
            raise Exception(f"FAILED TO RETRIEVE COGNITO TOKEN: {e}")

    def get_aws_caller_identity(self, audience: str, aws_cred: Optional[dict] = None, http_method: str = "POST"):
        # https://cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds#advanced_scenarios
        # Generate a signed request for the AWS STS GetCallerIdentity endpoint.
        # Used for token exchange between AWS and GCP (identity federation)
        request = AWSRequest(
            method=http_method,
            url="https://sts.amazonaws.com/?Action=GetCallerIdentity&Version=2011-06-15",
            headers={
                "Host": "sts.amazonaws.com",
                "x-goog-cloud-target-resource": audience,
            },
        )
        temp_cred = self.get_aws_cred_session(aws_cred)
        # https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html
        SigV4Auth(temp_cred, "sts", AWS_US_REGION).add_auth(request)

        # Create token from signed request.
        token = {
            "url": request.url,
            "method": request.method,
            "headers": [{"key": key, "value": value} for key, value in request.headers.items()],
        }
        return urllib.parse.quote(dumps(token, separators=(",", ":"), sort_keys=True))

    def get_gcp_sts_token(
        self, audience: str, subject_token: str, gcp_sts_url: str = "https://sts.googleapis.com/v1/token"
    ):
        # https://cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds#advanced_scenarios
        # Used to convert AWS STS token into GCP STS token
        grant_type = "urn:ietf:params:oauth:grant-type:token-exchange"
        requested_token_type = "urn:ietf:params:oauth:token-type:access_token"
        subject_token_type = "urn:ietf:params:aws:token-type:aws4_request"
        scope = "https://www.googleapis.com/auth/cloud-platform"

        gcp_sts_payload = {
            "audience": audience,
            "grant_type": grant_type,
            "requested_token_type": requested_token_type,
            "scope": scope,
            "subject_token_type": subject_token_type,
            "subject_token": subject_token,
        }
        try:
            response = httpx.post(gcp_sts_url, data=gcp_sts_payload)
            response.raise_for_status()
            return response.json().get("access_token")
        except Exception as e:
            raise Exception(f"FAILED TO RETRIEVE GCP STS TOKEN: {e}")

    def gcp_impersonate_token(self, sa_email: str, gcp_token: str):
        # https://cloud.google.com/iam/docs/workload-identity-federation-with-other-clouds#advanced_scenarios
        # Used to obtain access token for a specific Service Account on GCP
        url = f"https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/{sa_email}:generateAccessToken"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        payload = {"scope": ["https://www.googleapis.com/auth/cloud-platform"]}
        if self.debug:
            payload["lifetime"] = "10s"
        try:
            response = httpx.post(url, headers=headers, json=payload, auth=BearerAuth(gcp_token))
            response.raise_for_status()
            return response.json()
        except Exception as e:
            raise Exception(f"FAILED TO GENERATE IMPERSONATED GCP TOKEN: {e}")

    def remote_storage(self, cloud_vendor: str, client_id: Optional[str] = None, az_acc_name: Optional[str] = None):
        cs = None
        if cloud_vendor == "aws":
            # AWS creds are automatically injected into giver infra
            # Narwhal infra needs to grab the creds
            # On Giver ONLY --> hub_prod role is the default execution role
            # hub_prod also enables multicloud storage with client's S3 buckets
            cs = mc.CloudStorage(cloud_vendor=cloud_vendor)
            cs.cred_info = mc.AWSCredInfo()
            if self.infra_type == "narwhal":
                aws_secret = literal_eval(self.get_secret("AWS_SAMA_PROD"))
                cs.cred_info.id = aws_secret["id"]
                cs.cred_info.secret = aws_secret["key"]

        # client id is required to retrive the relvant metadata per cloud vendor
        # in order to setup offical multicloud storage
        elif client_id:
            cs = mc.CloudStorage(cloud_vendor=cloud_vendor)
            if cs.cloud_vendor == "gcp":
                # https://googleapis.dev/python/google-auth/latest/user-guide.html
                # https://google-auth.readthedocs.io/en/master/reference/google.auth.aws.html
                if cs.cred_info is None:
                    sa_email = self.get_sama_acc_info(client_id=client_id, cloud_vendor=cloud_vendor)
                    cs.cred_info = mc.GCPCredInfo(sa_email=sa_email, refresh_mode="external")
                self.generate_access_token(cs.cred_info)
            elif cs.cloud_vendor == "azure":
                cid, tid, auto_az_acc_name = self.get_sama_acc_info(client_id=client_id, cloud_vendor=cloud_vendor)
                az_token = ClientAssertionCredential(
                    tenant_id=tid, client_id=cid, func=self.get_cognito_token
                ).get_token(*AZ_TARGET_SCOPES)
                cs.cred_info = mc.AZCredInfo(
                    account_name=az_acc_name or auto_az_acc_name,
                    credential=AZTokenCredential(az_token),
                    tenant_id=tid,
                    client_id=cid,
                )
        return cs

    def create_path(self, path_type: str = "base", filepath: Optional[Union[str, Path]] = None) -> Path:
        if path_type == "base":
            bpath = Path(BASE_PATH)
            return bpath.joinpath(filepath) if filepath else bpath
        elif path_type == "giver":
            gpath = Path(GIVER_BLOCK_STORAGE_PATH)
            return gpath.joinpath(filepath) if filepath else gpath
        elif path_type == "debug":
            apath = Path(__file__).parent.absolute()
            return apath.joinpath(filepath) if filepath else apath

    def get_remote_task_name(self, project_id: str, task_id: str, suffix: str = "gz", task_round: Optional[str] = None):
        """
        Returns the remote path for the stored task data from the narwhal gateway.

        Args:
            project_id (str): The ID of the project.
            task_id (str): The ID of the task.
            suffix (str, optional): The file extension suffix. Defaults to "gz".
            task_round (str, optional): The task round data. Defaults to None.

        Returns:
            str: The remote task path
        """
        return (
            f"{project_id}{DELMITER}{task_id}{DELMITER}{task_round}.{suffix}"
            if task_round
            else f"{project_id}{DELMITER}{task_id}.{suffix}"
        )

    def create_remote_path(self, filename: str) -> str:
        """
        Returns the default narwhal datastore remote path for a given file.

        Args:
            filename (str): The name of the file.

        Returns:
            str: The proper remote path for the file.
        """
        return f"{DATA_STORE}/{filename}"

    def get_secret(self, secret_name: str, version_id: str = "latest") -> str:
        """
        This function takes a secret name and version ID as input, and returns the secret value as a
        string

        Args:
            secret_name (str): The name of the secret you want to retrieve.
            version_id (str): The version of the secret to retrieve. If not specified, the latest version is
        retrieved.

        Returns:
            The secret data specified by secret name in string format.
        """
        cred = None
        if self.cred_info and self.cred_info.token:
            self.refresh_token_if_expired(cred_info=self.cred_info, cloud_vendor="gcp")
            cred = gcp_credentials(self.cred_info.token)
        secret_client = secretmanager.SecretManagerServiceClient(credentials=cred)
        secret_path = secret_client.secret_version_path(GCP_PROJECT_ID, secret_name, version_id)
        secret_data = secret_client.access_secret_version(name=secret_path)
        return secret_data.payload.data.decode("UTF-8")

    def get_access_key(self, key_type: str = "primary") -> str:
        """
        This function retrieves an access key based on the key type provided, either "primary" or
        "secondary".

        Args:
          key_type (str): A string parameter that specifies whether to retrieve the primary or secondary
        access key. It can only have two possible values: "primary" or "secondary". Defaults to primary

        Returns:
          a string which is the access key.
        """
        if key_type not in ["primary", "secondary"]:
            raise Exception("INVALID KEY TYPE!")
        secret_name = "HUB_ACCESS_KEY" if key_type == "primary" else "HUB_INTERNAL_KEY"
        if access_key := os.getenv(secret_name) or self.get_secret(secret_name):
            return access_key
        raise Exception(f"COULD NOT RETRIEVE {key_type.upper()} ACCESS KEY!")

    def get_storage(
        self,
        cloud_vendor: Optional[str] = DEFAULT_CLOUD_VENDOR,
        client_id: Optional[str] = None,
        set_self: bool = False,
        az_acc_name: Optional[str] = None,
    ) -> Optional[Tuple[mc.CloudStorage, AbstractFileSystem]]:
        """
        This helper function sets up the various flavours of fsspec
        """
        cv = cloud_vendor or self.cloud_vendor
        cs = self.remote_storage(cloud_vendor=cv, client_id=client_id, az_acc_name=az_acc_name)
        if cs is None:
            raise Exception(f"FAILED TO SETUP ClOUD STORAGE, PLEASE CHECK YOUR INPUTS!")

        fs = (
            FSProxy(cs.get_fs(), lambda: self.refresh_token_if_expired(cred_info=cs.cred_info, cloud_vendor=cv))
            if cv in {"gcp", "azure"}
            else cs.get_fs()
        )
        if set_self:
            self.cs, self.fs = cs, fs
            return None
        else:
            return cs, fs

    def set_aws_cred(self):
        # kept for backwards compatibility
        warnings.warn("Use narcon.get_storage(set_self=True) instead", DeprecationWarning)
        self.get_storage(set_self=True)

    def store_task(self, task: dict, remote_path: str, add_prefix: bool = True):
        """
        Compresses and stores the given task data in the specified file path.

        Args:
            task (dict): The data to be stored.
            remote_path (str): The path or filename where the data will be stored.
            add_prefix (bool, optional): Add the data store prefix to the filename. Defaults to True.

        Returns:
            bool: True if the data was successfully stored, False otherwise.
        """
        r_path = self.create_remote_path(remote_path) if add_prefix else remote_path
        try:
            data_to_compress = JE.encode(task)
            with NamedTemporaryFile(suffix=".gz") as temp:
                with gzip.open(temp.name, "wb") as f:
                    f.write(data_to_compress)
                self.fs.put(temp.name, r_path)
            return True
        except Exception:
            return False

    def load_task(self, remote_path: str, add_prefix: bool = True):
        """
        It takes a path to a file on the cloud, downloads it to a temporary file, and then returns the contents of the file as a string

        Args:
            remote_path (str): The path or filename of the data you want to retrieve.
            datastore_prefix (bool, optional): Add the data store prefix to the filename. Defaults to True.

        Returns:
          The data from the remote location if exists, None otherwise.
        """
        r_path = self.create_remote_path(remote_path) if add_prefix else remote_path
        try:
            if self.fs.exists(r_path):
                with NamedTemporaryFile() as temp:
                    self.fs.get(r_path, temp.name)
                    with open(temp.name, "rb") as f:
                        return JD.decode(gzip.decompress(f.read()))
            return FileNotFoundError(f"FILE NOT FOUND: {r_path}")
        except Exception as e:
            return e

    def retrieve_task_sama_api(self, project_id: str, task_id: str, access_key: str) -> Optional[dict]:
        """
        This function retrieves a task from the Sama API

        Args:
          project_id (str): The ID of the project you want to retrieve the task from.
          task_id (str): The ID of the task you want to retrieve.
          access_key (str): The access key for the Sama API.

        Returns:
          A dictionary with the task information.
        """
        querystring = {"same_as_delivery": "true", "access_key": access_key}
        headers = {"Accept": "application/json"}
        url = f"https://api.sama.com/v2/projects/{project_id}/tasks/{task_id}.json"
        try:
            response = httpx.get(url, headers=headers, params=querystring)
            response.raise_for_status()  # raise exception if api query is not successful
            return response.json().get("task")  # return task json if api query is successful
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            message = e.response.json().get("message", "No message provided")
            return f"Task retrieval failed with error: {status_code} {message}"
        except Exception as e:
            return f"An unexpected error occurred: {str(e)}"

    def get_task(
        self,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
        task_round: Optional[str] = None,
        access_key: Optional[str] = None,
        delivery: bool = False,
    ) -> Optional[dict]:
        """
        Retrieves the task data from cloud storage or via the Sama API
        """
        pid = project_id or self.project_id
        tid = task_id or self.task_id

        if pid and tid:
            # Get the remote task name
            r_path = self.get_remote_task_name(project_id=pid, task_id=tid, task_round=task_round)

            # Try to load the task data from the remote path
            task_data = self.load_task(remote_path=r_path)

            # If task data is not found and delivery is enabled, try to retrieve it using the Sama API
            if isinstance(task_data, Exception) and delivery:
                task_data = self.retrieve_task_sama_api(
                    project_id=pid, task_id=tid, access_key=access_key or self.get_access_key()
                )

            if isinstance(task_data, Exception):
                raise task_data
            return task_data
        else:
            raise Exception("MISSING PROJECT OR TASK ID!")

    # TODO remove this function
    # def get_delivery_task(
    #     self,
    #     access_key: Optional[str] = None,
    #     project_id: Optional[str] = None,
    #     task_id: Optional[str] = None,
    # ) -> dict:
    #     """
    #     Retrieves the task data from cloud storage or by using the Sama API
    #     """
    #     warnings.warn("Use get_task(project_id=project_id, task_id=task_id, delivery=True) instead", DeprecationWarning)
    #     return self.get_task(project_id=project_id, task_id=task_id, access_key=access_key)

    def send_dpp(
        self,
        task: dict,
        project_id: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> bool:
        """
        The function sends the task data back to the SamaHub (KIKI Backend) to be processed
        """
        pid = project_id or self.project_id
        tid = task_id or self.task_id
        task_data = msgspec.structs.asdict(self.rt_validate(struct=task, struct_type=DPPTask))
        kiki_url, dpp_url = "KIKI_BASE_URL_PROD", "DPP_KEY_PROD"

        if base_url := os.getenv(kiki_url) or self.get_secret(kiki_url):
            endpoint_url = f"{base_url}api/v1/projects/{pid}/tasks/{tid}/post_processed"
            if key := os.getenv(dpp_url) or self.get_secret(dpp_url):
                try:
                    response = httpx.put(
                        endpoint_url,
                        auth=BearerAuth(key),
                        json=task_data,
                    )
                    response.raise_for_status()
                    return True
                except httpx.HTTPStatusError as err:
                    raise Exception(f"FAILED TO SEND DPP REQUEST: {err.response.status_code} {e.response.reason}")
                except Exception as e:
                    raise Exception(f"GENERAL EXCEPTION: {e}")

        if not base_url or not key:
            missing = []
            if not base_url:
                missing.append(kiki_url)
            if not key:
                missing.append(dpp_url)
            raise KeyError(f"MISSING REQUIRED VALUES: {', '.join(missing)}")
