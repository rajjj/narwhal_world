# Examples

## Flow invocation and variable passing
!!! note
    In the past you may have been used to using BaseModel for your parameters. <br>
    However going forward you must switch to using BaseSettings. <br>

!!! tip
    If your local environment is missing the dotenv package: <br>
    ```bash
    uv add --dev python-dotenv
    ```

!!! warning
    If you are using Pydantic 1 or libnar 3.x.x you must use the following import statement: <br>
    ```python
    from pydantic import BaseSettings
    ```

```python
from prefect import flow, task, get_run_logger
from pydantic_settings import BaseSettings
from pydantic import SecretStr
from typing import Optional

# Replace BaseModel with BaseSettings
class Param(BaseSettings):
    project_id: str
    task_id: str
    access_key: Optional[SecretStr]
    debug: bool = False

@flow(name = "<script_name>", log_prints = True)
def main(param: Param):
    print(param)

#==============================================================
# FUNCTION INNOVCATION
#===============================================================
# To test locally create a .env file and add your parameters to it
if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv() # if .env in same location as python file
    # load_dotenv("<path_to_.env_file>") # if in different location
    param = Param()
    main(param)
```
### Contents of the .env file

!!! tip
    Create the `.env` file in the same directory as your python file

```
    project_id=1200
    task_id="task_id"
    access_key="1120000"
    debug=False
```

## General Prefect Flow Example

```python
from prefect import flow, task, get_run_logger
# IMPORT BASESETTINGS!
from pydantic SecretStr
from typing import Optional
# You must have libnar installed
# Without libnar you NPS flows will fail to build
from libnar import libnar

# For any function you create add the task decorator if you want the Prefect UI to display it
# Functions that get called multiple times or in loops
# I recommend not adding task decorators to them as it will clutter the UI
@task
def print_str(str_to_print):
    print("HELLO NPS!")
    print(str_to_print)

# In Prefect we use pydantic classes to define the set of parameters the script can take it
# Note: Prefect cannot use click parameters you must convert your click data
# I recommend you comment out yout click parameters rather than delete them
# for more information on how to create parameters see the pydantic documentation
class Param(BaseSettings):
    project_id: str
    task_id: str
    access_key: Optional[SecretStr]
    debug: bool = False

# Prefect requires the flow decorator on your main function
# NOTE: YOUR start function must always be called main
# This is the start point for execution and flow control of your script
# NOTE: adding the log_prints=True specifier is optional
# this flag will redirect all print statement output to the prefect logger
@flow(name = "<script_name>", log_prints = True)
def main(param: Param):

    # The Prefect logger which can be used to display logging messages to the Prefect Web UI
    # This gives you fine grained control of the log level
    # ex: logger.info("print something")
    # you can also specify the log level
    # for errors: logger.error(<msg>)
    # for warnings: logger.warning(<msg>)
    # for debug: logger.debug(<msg)
    logger = get_run_logger()

    # In order to retrieve data from a secret string
    # you must use the .get_secret_value() method
    access_key = param.access_key.get_secret_value()

    # call function
    print_str("NAR NAR NAR")
```
[Flow invocation & variable passing](#flow-invocation-and-variable-passing)


## Webhook Event Source Example

### Using the Delivery Webhook

```python
from prefect import flow, task, get_run_logger
# IMPORT BASESETTINGS!
from pydantic import SecretStr
from typing import Optional
from libnar import libnar

# When using webhook event source you MUST have the following parameters: project_id and task_id
# access_key is only needed for local testing hence why it is optional
class Param(BaseModel):
    project_id: str
    task_id: str
    access_key: Optional[SecretStr]

# Prefect requires the flow decorator on your main function
# NOTE: YOUR start function must always be called main
# NOTE: adding the log_prints=True specifier is optional
# This flag will redirect all print statement output to the prefect logger
@flow(name = "<script_name>", log_prints = True)
def main(param: Param):

    # Invoke libnar and set the project_id and task_id
    narcon = libnar.Narcon()

    # Setup fsspec for the internal AWS
    narcon.get_storage(set_self=True)

    # Task_data will be returned as a dictionary
    # If you are testing locally you can pass in your client access key
    # The production environment does not require an access key
    task_data = narcon.get_task(
        project_id=param.project_id,
        task_id=param.task_id,
        delivery=True,
        access_key=param.access_key)

    # YOUR CODE GOES HERE
    # You are free to do whatever you want in your script from this point on

#==============================================================
# FUNCTION INNOVCATION
#===============================================================
# To test locally mock up some data to feed into your script:
# Before you push your code make sure you comment out this section!
if __name__ == '__main__':
    param_data = {
    "task_id": "task_id",
    "project_id": 1, # enter your project id here
    "access_key": "client access key", # local testing
}
    main(param_data)
```
[Flow invocation & variable passing](#flow-invocation-and-variable-passing)

### Using Other Webhook Types

```python
from prefect import flow, task, get_run_logger
# IMPORT BASESETTINGS!
from libnar import libnar

# When using webhook event source you MUST have the following parameters: project_id and task_id
class Param(BaseSettings):
    project_id: str
    task_id: str

# Prefect requires the flow decorator on your main function
# NOTE: YOUR start function must always be called main
# NOTE: adding the log_prints=True specifier is optional
# This flag will redirect all print statement output to the prefect logger
@flow(name = "<script_name>", log_prints = True)
def main(param: Param):

    # Invoke libnar and set the project_id and task_id
    narcon = libnar.Narcon()

    # Setup fsspec for the internal AWS
    narcon.get_storage(set_self=True)

    # Task_data will be returned as a dictionary
    task_data = narcon.get_task(
        project_id=param.project_id,
        task_id=param.task_id)

    # YOUR CODE GOES HERE
    # You are free to do whatever you want in your script from this point on
```

## DPP Event Source Example

!!! tip
    The class definition below is not needed in your code it just illustrates the dictionary you need to send back to the DPP event source.

    ```python
    class DPPTaskData(BaseModel):
        round: int
        answers: dict
        data: dict
    ```

```python
from prefect import flow, task, get_run_logger
I# IMPORT BASESETTINGS!
from libnar import libnar

# When using DPP as the event source you MUST have the following parameters: project_id, task_id and round
class Param(BaseModel):
    project_id: str
    task_id: str
    round: int

# Prefect requires the flow decorator on your main function
# NOTE: YOUR start function must always be called main
# NOTE: adding the log_prints=True specifier is optional
# This flag will redirect all print statement output to the prefect logger
@flow(name = "<script_name>", log_prints = True)
def main(param: Param):

    # Set the prefect logger
    logger = get_run_logger()

    # Invoke libnar and set the project_id and task_id
    narcon = libnar.Narcon()

    # Setup fsspec for the internal AWS
    narcon.get_storage(set_self=True)

    # Task_data will be returned as a dictionary
    task_data = narcon.get_task(
        project_id=param.project_id,
        task_id=param.task_id,
        task_round=param.round)

    # The DPP JSON is slighty different then the delivery JSON format
    # project_id: str
    # id: str
    # round: int
    # answers: dict
    # data: dict

    # Typically your code would modify the answers section of the task json
    # You can also modify the data section
    ans_data = task_data["answers"]

    # YOUR CODE GOES HERE
    # Assuming you apply some operation to the answer data
    modified_ans_data = ans_data
    task_data["answers"] = modified_ans_data

    # The modified task data MUST be returned to the SamaHub
    # You can accomplish by invoking the send_dpp function
    # The modified task will be stored for retrieval via the delivery endpoint
    if narcon.send_dpp(task=task_data):
        print("Successfully sent DPP task data!")
    else:
        logger.error("Failed to send DPP task data!")
```
[Flow invocation & variable passing](#flow-invocation-and-variable-passing)
