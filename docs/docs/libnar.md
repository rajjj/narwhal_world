# Libnar

!!! note
    In order to install the libnar package make sure your project has access to the [private python repo](private_pypi.md) <br> <br>
    Please do not install the packages listed below separately. <br>
    Doing so can result in conflicts with the libnar package and lead to build failures.

Extra dependencies (not installed by default):

```bash
uv add libnar --extra <alias>
```

=== "libnar 4.x.x"

    ```bash
    uv add libnar
    ```

    | Library | Description | Extra Dependency | Alias |
    | --- | --- | --- | --- |
    | pydantic-settings | Settings management | No | - |
    | httpx and requests | HTTP library | No | - |
    | s3fs | fsspec implementation for AWS storage | No | - |
    | google-cloud-secret-manager | Secret retrieval from GCP Secret Manager | No | - |
    | boto3 | Python SDK to access AWS services | No | - |
    | msgspec | Serialization library | No | - |
    | pymongo | Python SDK to create objectIDs for pre-processing | No | - |
    | google-auth | Google authentication library | No | - |
    | slack-sdk | Slack SDK | No | - |
    | gcsfs | fsspec implementation for Google storage | No | - |
    | aldfs | fsspec implementation for Azure storage | No | - |
    | pycopg | Postgres adapter/driver | Yes | db |
    | sqlalchemy | ORM for SQL databases | Yes | db |
    | azure-identity | Azure Identity client library | No | - |

    <!-- | cloud-sql-python-connector | SQL database connector for GCP databases | Yes | db| -->


=== "libnar 3.x.x"

    ```bash
    uv add libnar==3.2.0
    ```

    | Library | Description | Extra Dependency | Alias |
    | --- | --- | --- | --- |
    | pydantic v1 | Data validation and settings management in Prefect | No | - |
    | requests | HTTP library | No | - |
    | s3fs | fsspec implementation for AWS storage | No | - |
    | gcsfs | fsspec implementation for Google storage | Yes | gcsfs |
    | aldfs | fsspec implementation for Azure storage | Yes | aldfs |
    | google-cloud-secret-manager | Secret retrieval from GCP Secret Manager | No | - |
    | boto3 | Python SDK to access AWS services | No | - |
    | pymongo | Python SDK to create objectIDs for pre-processing | No | - |
    | google-auth | Google authentication library | No | - |

## Invoking libnar

```python
from libnar import libnar

def main():

    # Invoke libnar and store project_id and task_id
    narcon = libnar.Narcon(project_id=param.project_id, task_id=param.task_id)

    # Alternative way to invoke libnar
     narcon = libnar.Narcon()

    # You can also set the project id and task id after object creation
    narcon.set_project_data(project_id=param.project_id, task_id=param.task_id)
```

## Retrieving the Primary & Secondary Access Key(s)

!!! note
    The primary key is also known as the universal client access key <br>
    The secondary key is also known as the internal developer access key <br>
    The secondary key is used to access the internal developer APIs

```python
from libnar import libnar

def main():

    narcon = libnar.Narcon()

    # This will return the primary key
    # You may leave out the key_type parameter as it defaults to "primary"
    access_key = narcon.get_access_key(key_type="primary")

    # In order to get the secondary key do this
    secondary_key = narcon.get_access_key(key_type="secondary")
```

## Remote Storage Access

!!! note
    Offical multicloud storage integration support <br>
    Internal refers to SamaHub's internal S3 storage <br>
    External refers to a client's cloud storage

### Accessing internal/external AWS storage

```python
from libnar import libnar

def main():
    narcon = libnar.Narcon()

    # Allows the flow to access production data on S3
    # This function does not set credentials outside of a authorized production environment
    # Full innovation: narcon.get_storage(cloud_vendor="aws", set_self=True)
    # cloud_vendor is set as aws by default so you can leave it out
    # Only works on libnar 4.0.0
    narcon.get_storage(set_self=True)

    # Alternatively you can also directly retrieve the filesystem object
    # Full innovation: narcon.get_storage(cloud_vendor="aws")
    # cloud_vendor is set as aws by default so you can leave it out
    _, aws_fs = narcon.get_storage()

    # This function is kept for backward compatibility
    # Note: This function will be deprecated once libnar 4.0.0 is released
    narcon.set_aws_cred()
```

### Accessing external GCP/Azure storage
![Requires libnar 4.0.0](https://img.shields.io/badge/Requires%20libnar-4.0.0-blue)

!!! info
    `client_id` is the client specific id  that is set in the SamaHub <br>
    `cloud_vendor` can be set to either `aws`, `gcp` or  `azure`. By default `cloud_vendor` is set as `aws` <br>
    Select the correct cloud vendor based on which cloud storage the client is using. <br><br>

```python
from libnar import libnar

def main():
    narcon = libnar.Narcon()
    # Access gcp storage
    _, gcs_fs = narcon.get_storage(cloud_vendor="gcp", client_id="1344")
    # Access azure storage
    _, az_fs = narcon.get_storage(cloud_vendor="azure", client_id="1344")
```

!!! warning
    This multicloud functionality cannot be used in your local environment. Please use in a secure environment.

### Using fsspec

See the [fsspec cheatsheet](fsspec_cheatsheet.md) for more information on how to use fsspec.

```python
from libnar import libnar

def main():

    # libnar automatically sets up fsspec for an appropriate cloud vendor
    narcon = libnar.Narcon()

    # use get_storage to get the filesystem object
    <get_storage>

    # You can call fsspec functions like this fs.<fsspec func name>
    fs.ls("some-random-bucket/")

```

## Accessing data from secret manager

!!! info
    Your environment and access level determines the types of secrets that can be accessed from the secret manager.<br>

    There are two types of secrets:
    <ol>
        <li>System secrets</li>
        <ul>
            <li>Accessible only to admins</li>
            <li>Can only be used in a secure environment</li>
        </ul>
        <li>Client secrets</li>
        <ul>
            <li>Accessible to anybody with access to Narwhal GCP</li>
            <li>Secret name starts with CS</li>
            <li>Can be used for local testing</li>
        </ul>
    </ol>

```python
from libnar import libnar
from ast import literal_eval

def main():
    narcon = libnar.Narcon()

    secret_string = narcon.get_secret("name_of_secret")

    # All data in secret manager is stored as a string
    # If you need to retrive JSON data you will have to convert it back
    # In order to convert it back to a dict you can do the following:
    secret_dict = literal_eval(secret_string)
```


## Accessing the base/root filepath

!!! note
    base_path is the starting path when a flow is run in a production environment.

```python
from libnar import libnar

def main():
    narcon = libnar.Narcon()

    # Retrive the base_path as a Path object
    base_path = narcon.create_path()

    # You can use this handy function to generate new paths
    # new_path will be of type pathlib.Path
    # path_type = "base" is optional
    prod_path = narcon.create_path(path_type="base", filepath="path_to_file")

    # You can use this handy function to generate new paths
    # new_path will be of type pathlib.Path
    prod_path = narcon.create_path(path_type="giver", filepath="path_to_file")

    # When debugging on your local machine use the debug flag for convenience
    # This flag sets the root of your folder as the "basepath"
    # Make sure to remove the debug flag when you go into production
    local_path = narcon.create_path(path_type="debug", filepath="path_to_file")
```
<br>

## Reading and Writing JSON

![Requires libnar 4.0.0](https://img.shields.io/badge/Requires%20libnar-4.0.0-blue)

For more details see the [msgspec website](https://jcristharif.com/msgspec/)

```python
from libnar import libnar

def main():
    # This is very fast implementation of reading and writing JSON
    # It uses the msgspec library to serialize and deserialize JSON
    narcon = libnar.Narcon()

    # Read JSON
    json_data = narcon.read_json("path_to_file")

    # Write JSON
    narcon.write_json("path_to_file", json_data)
```

## Sending a Slack message to a channel

![Requires libnar 4.0.0](https://img.shields.io/badge/Requires%20libnar-4.0.0-blue)
!!! info
    You can add fancy formatting to your slack message by using the [Block Kit Builder](https://app.slack.com/block-kit-builder) <br>
    You can also simply pass in a string as the message

```python
from libnar import libnar

def main():
    narcon = libnar.Narcon()
    # Using block kit
    msg_body = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"@here WELCOME TO THE FUTURE!
                },
            }
        ]
    # Returns True if message was sent successfully
    # Returns an error message if the message failed to send
    msg_status = narcon.notify_slack_channel(msg_body=msg_body, channel="narwhals")

    if msg_status != True:
        # either raise exception or print error message
        raise Exception(msg_status)
        # print(msg_status)
```

### Sending a Slack message with an attachment

![Requires libnar 4.0.0](https://img.shields.io/badge/Requires%20libnar-4.0.0-blue)
```python
from libnar import libnar

def main():
    # Single file upload
    # Not using block kit
    msg_body = "This message has a file attachment"
    narcon = libnar.Narcon()
    if not narcon.notify_slack_channel(msg_body=msg_body, channel="narwhals", uploads="path_to_file"):
        raise Exception("FAILED TO SEND SLACK MESSAGE!")

    # For multiple files use a list
    # Returns True if message was sent successfully
    # Returns an error message if the message failed to send
    msg_status = narcon.notify_slack_channel(msg_body=msg_body, channel="narwhals", uploads=["path_to_file", "path_to_file2"])

    if msg_status != True:
        # either raise exception or print error message
        raise Exception(msg_status)
        # print(msg_status)
```

## Database access

![Requires libnar 4.0.0](https://img.shields.io/badge/Requires%20libnar-4.0.0-blue)

```bash
uv add libnar --extra db
```

=== "AWS"
    !!! info
        For more information about how to use the database connector: <br>
        [Pycopg](https://www.psycopg.org/psycopg3/) <br>
        [SQLAlchemy](https://docs.sqlalchemy.org/en/)

    ```python
    from libnar import libnar
    import sqlalchemy

    def main():
        narcon = libnar.Narcon()
        engine = narcon.db_connect()
        metadata = sqlalchemy.MetaData()
        with engine.connect() as conn:
            metadata.reflect(bind=conn)
            for table in metadata.tables.values():
                print(table.name)
    ```

=== "GCP -DO NOT USE"
    !!! info
        For more information about how to use the database connector: <br>
        [Google SQL Connector](https://github.com/GoogleCloudPlatform/cloud-sql-python-connector) <br>
        [SQLAlchemy](https://docs.sqlalchemy.org/en/)

    ```python
    from libnar import libnar
    from google.cloud.sql.connector import Connector
    import sqlalchemy

    def main():
        narcon = libnar.Narcon()

        with Connector() as connector:
        # initialize connection pool
            engine = narcon.db_connect(connector)
            metadata = sqlalchemy.MetaData()
            with engine.connect() as conn:
                metadata.reflect(bind=conn)
                for table in metadata.tables.values():
                    print(table.name)
    ```

## Help

### Running into authorization issues when trying to install libnar

See [Private python repo](private_pypi.md#faq) for details on how to resolve this issue.
