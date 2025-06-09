import json
import os
import tempfile
from pathlib import Path

import adlfs
import gcsfs
import pydantic
import pytest
import requests_mock
import s3fs
from libnar.libnar import *


@pytest.fixture
def narcon():
    return Narcon()


@pytest.fixture
def test_task():
    # Create a temporary JSON file with test data and yield the path to the file.
    test_data = {"test": "data"}
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
        json.dump(test_data, f)
    yield f.name


def test_giver_msg_type_complete():
    # Test that the "COMPLETE" message type is defined correctly
    assert MsgType.COMPLETE == "completed"


def test_giver_msg_type_fail():
    # Test that the "FAIL" message type is defined correctly
    assert MsgType.FAIL == "failure"


def test_giver_message_no_data():
    # Test that a valid input message object can be created with default values
    message = GiverMessage(id="123", message="test", msg=MsgType.COMPLETE)
    assert message.msg == MsgType.COMPLETE
    assert message.id == "123"
    assert message.message == "test"
    assert message.data == {}


def test_giver_message_data():
    # Test that the optional data attribute can be set
    data = {"a": 1, "b": 2}
    message = GiverMessage(id="123", message="test", data=data, msg=MsgType.COMPLETE)
    assert message.data == data


def test_giver_message_invalid_message():
    # Test that the message attribute is required
    with pytest.raises(pydantic.error_wrappers.ValidationError):
        GiverMessage(id="123")

    # Test that the message attribute can only be a string
    with pytest.raises(pydantic.error_wrappers.ValidationError):
        GiverMessage(message=123)


def test_bearer_auth():
    # Test that a BearerAuth object can be created with a token
    auth = BearerAuth("my_token")
    assert isinstance(auth, requests.auth.AuthBase)

    # Test that the __call__ method adds the correct authorization header to a request
    request = requests.Request("GET", "http://example.com")
    prepared_request = request.prepare()
    prepared_request = auth(prepared_request)
    assert prepared_request.headers["authorization"] == "Bearer my_token"


def test_narcon_defaults(narcon):
    # Test that a NarCon object is created with default values
    assert narcon.project_id is None
    assert narcon.task_id is None
    assert isinstance(narcon.fs, (s3fs.S3FileSystem, gcsfs.GCSFileSystem, adlfs.AzureBlobFileSystem))
    assert narcon.cloud_vendor == DEFAULT_CLOUD_VENDOR


def test_narcon_post_init(mocker, narcon):
    # Test that the __post_init__ method calls set_remote_fs
    set_remote_fs_mock = mocker.patch.object(narcon, "set_remote_fs")
    narcon.__post_init__()
    set_remote_fs_mock.assert_called_once()


def test_narcon_set_attribute(narcon):
    # Test that an attribute of a Narcon object can be set
    narcon.project_id = "new_project_id"
    assert narcon.project_id == "new_project_id"


def test_set_remote_fs_aws_no_credentials():
    # Test set_remote_fs with cloud_vendor="aws" and no AWS credentials
    narcon = Narcon(cloud_vendor="aws")
    narcon.set_remote_fs()
    assert isinstance(narcon.fs, s3fs.S3FileSystem)
    assert narcon.fs.anon is False


def test_set_remote_fs_aws_with_credentials():
    # Test set_remote_fs with cloud_vendor="aws" and AWS credentials
    narcon = Narcon(cloud_vendor="aws")
    narcon.set_remote_fs(aws_id="my_access_key", aws_secret="my_secret_key")
    assert isinstance(narcon.fs, s3fs.S3FileSystem)
    assert narcon.fs.anon is False


def test_set_remote_fs_gcp():
    # Test set_remote_fs with cloud_vendor="gcp"
    narcon = Narcon(cloud_vendor="gcp")
    narcon.set_remote_fs()
    assert isinstance(narcon.fs, gcsfs.GCSFileSystem)
    assert narcon.fs.project == GCP_PROJECT_ID


def test_set_cloud_vendor_valid(narcon):
    # Test that set_cloud_vendor sets the cloud_vendor attribute to a valid value
    narcon.set_cloud_vendor("aws")
    assert narcon.cloud_vendor == "aws"


def test_set_cloud_vendor_invalid(narcon):
    # Test that set_cloud_vendor raises an exception for an invalid cloud_vendor
    with pytest.raises(Exception):
        narcon.set_cloud_vendor("invalid_vendor")


def test_create_path_base_no_filepath(narcon):
    # Test create_path with path_type="base" and no filepath
    path = narcon.create_path()
    assert isinstance(path, Path)
    assert str(path) == BASE_PATH


def test_create_path_base_with_filepath(narcon):
    # Test create_path with path_type="base" and a filepath
    path = narcon.create_path(filepath="test.txt")
    assert isinstance(path, Path)
    assert str(path) == f"{BASE_PATH}/test.txt"


def test_create_path_giver_no_filepath(narcon):
    # Test create_path with path_type="giver" and no filepath
    path = narcon.create_path(path_type="giver")
    assert isinstance(path, Path)
    assert str(path) == GIVER_BLOCK_STORAGE_PATH


def test_create_path_giver_with_filepath(narcon):
    # Test create_path with path_type="giver" and a filepath
    path = narcon.create_path(path_type="giver", filepath="test.txt")
    assert isinstance(path, Path)
    assert str(path) == f"{GIVER_BLOCK_STORAGE_PATH}/test.txt"


def test_set_project_data(narcon):
    # Test that set_project_data sets the project_id and task_id attributes correctly

    narcon.set_project_data(project_id=1, task_id="my_task_id")
    assert narcon.project_id == 1
    assert narcon.task_id == "my_task_id"

    # project id must be a valid int
    with pytest.raises(pydantic.error_wrappers.ValidationError):
        narcon.set_project_data(project_id="my_project_id", task_id="my_task_id")


def test_create_blob_name(narcon):
    # Test that create_blob_name returns the expected blob name
    project_id = "my_project_id"
    task_id = "my_task_id"
    suffix = "txt"
    expected_blob_name = f"{project_id}{DELMITER}{task_id}.{suffix}"
    assert narcon.create_blob_name(project_id, task_id, suffix) == expected_blob_name


def test_create_blob_path(narcon):
    # test when all parameters are passed
    assert (
        narcon.create_blob_path("project_id", "task_id", "blob_name", True, "gz")
        == "sama-narwhal-data-store/temp/blob_name"
    )
    # test when blob_name is not passed and use_temp is False
    assert (
        narcon.create_blob_path("project_id", "task_id", None, False, "gz")
        == "sama-narwhal-data-store/project_id--task_id.gz"
    )
    # test when blob_name is not passed and use_temp is True
    assert (
        narcon.create_blob_path("project_id", "task_id", None, True, "gz")
        == "sama-narwhal-data-store/temp/project_id--task_id.gz"
    )


def test_get_secret(narcon):
    # Test that get_secret returns the expected secret value
    secret_name = "CS_TEST"
    expected_secret_value = "HELPME"
    assert narcon.get_secret(secret_name) == expected_secret_value


def test_get_access_key_primary(narcon):
    # Test that get_access_key returns the primary access key when key_type is "primary"
    os.environ["HUB_ACCESS_KEY"] = "primary_access_key"
    assert narcon.get_access_key(key_type="primary") == "primary_access_key"


def test_get_access_key_secondary(narcon):
    # Test that get_access_key returns the secondary access key when key_type is "secondary"
    os.environ["HUB_INTERNAL_KEY"] = "secondary_access_key"
    assert narcon.get_access_key(key_type="secondary") == "secondary_access_key"


def test_get_access_key_invalid_key_type(narcon):
    # Test that get_access_key raises an exception when an invalid key_type is provided
    with pytest.raises(Exception):
        narcon.get_access_key(key_type="invalid_key_type")


def test_set_aws_cred(mocker, narcon):
    # Test that AWS credentials are set correctly
    os.environ.pop("AWS_ACCESS_KEY_ID", None)
    os.environ.pop("AWS_SECRET_ACCESS_KEY", None)
    get_secret_mock = mocker.patch.object(Narcon, "get_secret", return_value=b'{"id": "dummy_id", "key": "dummy_key"}')
    narcon.set_aws_cred()
    get_secret_mock.assert_called_once_with("AWS_SAMA_PROD")
    assert os.getenv("AWS_ACCESS_KEY_ID") == "dummy_id"
    assert os.getenv("AWS_SECRET_ACCESS_KEY") == "dummy_key"
    os.environ.pop("AWS_ACCESS_KEY_ID", None)
    os.environ.pop("AWS_SECRET_ACCESS_KEY", None)


# @pytest.mark.skip(reason="Awaiting clarification on function usage - Issue #487")
def test_create_task_id(narcon):
    task_id = narcon.create_task_id()
    assert isinstance(task_id, str)
    assert len(task_id) == 24


@pytest.mark.skip(reason="Needs simulation of file retrieval from cloud")
def test_retrieve_task(mocker):
    # Test that the retrieve_task function retrieves the contents of a file from the cloud
    narcon = Narcon(cloud_vendor="aws")
    # Mock the fs object
    fs_mock = mocker.Mock()
    fs_mock.exists.return_value = True
    fs_mock.get.return_value = b"Hello, world!"
    narcon.fs = fs_mock
    r_path = "test/file/path"
    result = narcon.retrieve_task(r_path)
    assert isinstance(result, bytes)
    assert result == b"Hello, world!"

    # Test that the function returns None when the file doesn't exist
    fs_mock.exists.return_value = False
    result = narcon.retrieve_task(r_path)
    assert result is None

    # Test that the function returns None when there is an error retrieving the file
    fs_mock.exists.return_value = True
    fs_mock.get.side_effect = Exception()
    result = narcon.retrieve_task(r_path)
    assert result is None


def test_retrieve_task_sama_api(mocker, narcon):
    # Test that we can retrieve a task from the Sama API
    project_id = "test_project"
    task_id = "test_task"
    access_key = "test_access_key"
    task_info = {"id": task_id, "name": "test_name", "status": "completed"}
    response_mock = mocker.Mock()
    response_mock.ok = True
    response_mock.json.return_value = {"task": task_info}
    requests_get_mock = mocker.patch("requests.get", return_value=response_mock)
    assert narcon.retrieve_task_sama_api(project_id, task_id, access_key) == task_info
    requests_get_mock.assert_called_once_with(
        f"https://api.sama.com/v2/projects/{project_id}/tasks/{task_id}.json",
        headers={"Accept": "application/json"},
        params={"same_as_delivery": True, "access_key": access_key},
    )


def test_retrieve_task_sama_api_request_failure(mocker, narcon):
    # Test that we handle request failures correctly
    project_id = "test_project"
    task_id = "test_task"
    access_key = "test_access_key"
    response_mock = mocker.Mock()
    response_mock.ok = False
    requests_get_mock = mocker.patch("requests.get", return_value=response_mock)
    assert narcon.retrieve_task_sama_api(project_id, task_id, access_key) is None
    requests_get_mock.assert_called_once_with(
        f"https://api.sama.com/v2/projects/{project_id}/tasks/{task_id}.json",
        headers={"Accept": "application/json"},
        params={"same_as_delivery": True, "access_key": access_key},
    )


def test_retrieve_task_sama_api_exception(mocker, narcon):
    # Test that we handle exceptions correctly
    project_id = "test_project"
    task_id = "test_task"
    access_key = "test_access_key"
    requests_get_mock = mocker.patch("requests.get", side_effect=Exception("Test exception"))
    assert narcon.retrieve_task_sama_api(project_id, task_id, access_key) is None
    requests_get_mock.assert_called_once_with(
        f"https://api.sama.com/v2/projects/{project_id}/tasks/{task_id}.json",
        headers={"Accept": "application/json"},
        params={"same_as_delivery": True, "access_key": access_key},
    )


def test_create_giver_msg(narcon):
    narcon.task_id = "test_task_id"
    message = "Hello Giver!"
    sample_data = {"1": 2}
    task_id = "test_task_id"

    expected = {
        "msg": "completed",
        "id": narcon.task_id,
        "message": message,
        "data": sample_data,
    }
    result = narcon.create_giver_msg(message=message, data=sample_data, msg_type=MsgType.COMPLETE)
    assert result == json.dumps(expected)

    expected = {
        "msg": MsgType.COMPLETE.value,
        "id": task_id,
        "message": message,
        "data": sample_data,
    }
    result = narcon.create_giver_msg(message=message, data=sample_data, msg_type=MsgType.COMPLETE, task_id=task_id)
    assert json.loads(result) == expected


def test_get_task_with_path(narcon):
    test_data = {"test": "data"}
    with tempfile.NamedTemporaryFile(suffix=".json") as f:
        f.write(json.dumps(test_data).encode())
        f.seek(0)
        task_data = narcon.get_cpp_task(task_path=f.name)
        assert task_data == test_data

    with tempfile.NamedTemporaryFile() as f:
        f.write("not json data".encode())
        f.seek(0)
        with pytest.raises(Exception, match="task_path is not a json file!"):
            narcon.get_cpp_task(task_path=f.name)

    with pytest.raises(Exception, match="task_path does not exist!"):
        narcon.get_cpp_task(task_path="nonexistent_path.json")


def test_get_task_with_blob(narcon, test_task):
    test_data = {"test": "data"}
    task_data = narcon.get_cpp_task(task_path=test_task)
    assert task_data == test_data


@pytest.mark.skip(reason="Not needed for now")
def test_get_task_with_sama_api(narcon, mocker):
    test_data = {"test": "data"}
    access_key = "test_access_key"
    mocker.patch("libnar.libnar.Narcon.retrieve_task_sama_api", return_value=test_data)

    task_data = narcon.get_delivery_task(access_key=access_key)
    assert task_data == test_data
    assert narcon.retrieve_task_sama_api.call_count == 1


def test_get_task_no_data(narcon, mocker):
    mocker.patch("libnar.libnar.Narcon.retrieve_task", return_value=None)
    mocker.patch("libnar.libnar.Narcon.retrieve_task_sama_api", return_value=None)

    with pytest.raises(Exception, match="Could not retrieve the task data!"):
        narcon.get_delivery_task()
    assert narcon.retrieve_task_sama_api.call_count == 0


@pytest.mark.skip(reason="Not authorized to get secret")
def test_send_dpp_resp(narcon, mocker):
    task_data = {"round": 1, "data": {"test": "data"}, "answers": {"test": "data"}}
    secret_url, secret_key = "KIKI_BASE_URL", "DPP_KEY"
    base_url = narcon.get_secret(secret_url)
    key = narcon.get_secret(secret_key)

    with requests_mock.Mocker() as m:
        url = f"{base_url}api/v1/projects/{narcon.project_id}/tasks/{narcon.task_id}/post_processed"
        m.put(url, json={"success": True})

        result = narcon.send_dpp(task_data, 1)

    assert result is True
    assert m.call_count == 1
    assert m.request_history[0].url == url
    assert m.request_history[0].headers["Authorization"] == "Bearer test_secret"
    assert m.request_history[0].json() == task_data


@pytest.mark.skip(reason="Not needed for now")
def test_send_dpp_resp_error_handling(narcon, requests_mock):
    # Set up a mock response with status code 404 and custom reason
    task_id = "test_task"
    secret_url, secret_key = "KIKI_BASE_URL", "DPP_KEY"
    base_url = narcon.get_secret(secret_url)
    key = narcon.get_secret(secret_key)
    endpoint_url = f"{base_url}api/v1/projects/test_project/tasks/{task_id}/post_processed"
    requests_mock.put(endpoint_url, status_code=404, reason="Not Found")

    # Mock the environment variables
    with pytest.raises(Exception, match=r"FAILED TO SEND: 404 Not Found"):
        # Call the method with a mock task dictionary
        task = {"round": 1, "data": {"test": "data"}, "answers": {"test": "data"}}
        narcon.project_id = "test_project"
        narcon.task_id = task_id
        narcon.send_dpp(task, 1)
