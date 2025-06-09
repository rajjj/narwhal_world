# NPS Documentation

## Background about the new processing pipeline

NPS replaces the need to have multiple systems to automate the running of scripts.

The system provides following high level features: <br>

1. It can run scripts on schedules (cron job + advanced rules)
2. It can handle both pre-processing and post-processing tasks
3. Dynamically allocate more resources on the fly
4. Massively simplified build system (think AutoQA, but better)
5. Quickly test locally in a production like environment
6. Provides intuitive web interface to keep track of running scripts
7. Event system that can integrate with the Samahub

!!! tip
    For more details on the orchestration system see [Prefect](https://docs.prefect.io/)

## Getting started with the system

### Clone the main repo

1. Git clone the sol-eng repo:
```bash
git clone https://github.com/Samasource/soln-eng.git
```
2. Open the cloned repo in VSCode

3. Create a python package in the `flows` folder


| Folder name       | Purpose             |
|-------------------|---------------------|
| scripts           | This folder will contain raw scripts (No automation)
| flows             | This folder will contain NPS scripts (Automated)


!!! info
    <b>IT IS VERY IMPORTANT YOU FOLLOW THE GUIDELINES FOR NAMING SCRIPTS. <br>
    NON-COMPLIANCE CAN RESULT IN BUILD FAILURES!</b> <br>

    Scripts must be added to flows folder in order to trigger the Narwhal CI pipeline.

### Event source selection

Event sources allow retrieval of data from many different systems (ie: SamaHub). The data retrieved from the event source is then feed into NPS.

#### Event Source Requirements
In order to use event sources you must have the [libnar library](#libnar-library) installed. <br>
Some event sources may also require an additional gateway component.

| Event Source    |Libnar release | Narwhal Gateway|
|:--------------: |:-------------:|:-------------:|
| Webhook         | 3.0.0+        | REQUIRED       |
| DPP             | 3.0.0+         | REQUIRED       |


#### Webhook Event Source

The webhook event source will allow NPS to retrieve task data from a SamaHub configured webhook. This event source provides the most flexibility when working on post-processing workflows.<br>

- Use the webhook event source when,
    * You want to deliver data to a client in a format other than JSON
    * You want to automatically trigger your flows to process tasks based on all task states supported by SamaHub's webhook system
- <b>Do not</b> use the webhook event source if,
    * You require round data in the task delivery payload
    * You're doing something that requires use of the Sama API to trigger task creation

##### Configuring the Webhook Event Source

!!! info
    Ask your admin for the username and password to the Narwhal Gateway

1. Go to the SamaHub project you want to configure
2. Configure the delivery webhook
3. Set `Callback URL` to:
```bash
https://narwhal-gateway-me3asbybaq-uc.a.run.app/webhook-event
```
4. Set `Auth. Method` to `x-auth-token` on the webhook page
5. Generate a `Token` by going to the [Narwhal Gateway](https://narwhal-gateway-me3asbybaq-uc.a.run.app/api/rapidoc#put-/create-token)
6. The input field will be on the right hand side of the page, look for the `Send API Request` button.
7. Enter the name of your flow in the body field: ```{"name": "<name of your flow>"}```
8. Parameters are optional: used to pass any runtime additional parameters your flow requires.
9. Click `Send API Request`
10. Copy the generated token from response body
11. Add the token to the `Auth. Method` field on the webhook page
12. Save your webhook configuration

!!! example
    [Webhook Event Source Example](nps_examples.md#webhook-event-source-example)

#### Delivery Post Processing (DPP) Event Source

The DPP event source will allow NPS to retrieve task data from SamaHub. It is enabled by configuring the "Custom post-processing" tab. This event source is meant to be used on post-processing workflows. <br>

- Use the DPP event source when,
    * The client wants to retrieve a <b> modified </b> task data using the Sama API
    * You want to automatically trigger your flows to process tasks in the delivered state
- <b>Do not</b> use the DPP event source if,
    * You want to return data in a format that is not JSON
    * You want to return data that is JSON data, but does not match the DPP schema

##### Configuring the DPP Event Source
1. Go to the SamaHub project you want to configure
2. Click the `Custom post-processing` tab
3. `Enable custom post-processing` must be checked
4. Set `Service URL` to:
```bash
https://narwhal-gateway-me3asbybaq-uc.a.run.app/dpp-event
```
5. Enter the name of your flow in the `Script name` field (without the ".py" suffix)
6. Parameters are optional, but can be used to pass additional data to your flow
7. Save your configuration

!!! example
    [DPP Event Source Example](nps_examples.md#dpp-event-source-example)


#### Special Parameters

!!! note
    The special parameters listed below will work on the Webhook and DPP event sources.

If you have multiple deployments you can configure the system to point to a specific one:
```json
{"dep_name": "deployment_name"}
```

### Libnar library

See the [libnar page](libnar.md) for more details.

### Testing locally

!!! note
    If you are using the package creator you can skip step 1.

1. In order to test locally you will need to add prefect as a dev dependency:
```bash
uv add --dev prefect
```
2. Start your virtual environment
```bash
source .venv/bin/activate
```
3. Start the local webserver
```bash
prefect server start
```
4. Open a new terminal and execute your python code
```bash
python <script_name>
```
5. Check the results of your flow execution in the local web UI

!!! tip
    The default local server URL is: <http://127.0.0.1:8000>

### Deploying to production

#### Triggering the CI pipeline

1. Create a new branch for your flow (similar to the approach you take for AutoQA)
2. Commit all your changes to the branch
3. Push your code to the branch to trigger the CI Pipeline (Pipewhal)
!!! info
    Pipewhal will trigger anytime a change is pushed to the branch. <br>
    Merge requests do not trigger the pipeline. <br>


    If you do not want to trigger the pipeline you can add `[skip ci]` anywhere in the commit message <br>
    `My commit message [skip ci]`  OR  `[skip ci] My commit message`

!!! tip
    As good coding pratice you should merge your code into main periodically.


#### Checking the status of the build
1. Please login to [Codefresh](https://codefresh.io/) to see the progress of your build
2. Navigate to the `soln-eng` project and look for the `build_flows` pipeline
3. Click the `builds` tab and locate your build
!!! tip
    You can also get a link to the build by clicking the build indicator on the branch in Github


#### Logging into Prefect Cloud (Managed UI)

1. Once the build is complete, login to [Prefect cloud](https://app.prefect.cloud/)
2. Once you are logged in click the workspaced entitled "nps-prod"
3. Verify that the flow is registered and the settings are correct


### Configuration Settings

The NPS build system can read a specific section called `sama-build` in the pyproject.toml file. The `sama-build` section is used to set extra configuration values for a flow.

#### amount

The amount option is used to set the resource limits for your flow.

!!! info
    If amount is not set the system will use the "low" preset by default. <br>
    For most scripts "low" and "med" presets will be sufficent. <br>
    The "very-high" preset represents the current max amount of CPU and RAM you can allocate per instance. <br>

    Narwhal infra is powered by ECS fargate refer to the [fargate config guide](https://docs.aws.amazon.com/eks/latest/userguide/fargate-pod-configuration.html) for information on cpu/mem limits.

    Disk (storage space) will change depending on the [infrastructure](#infra) your flow is running on.

    Base storage = main storage for the container <br>
    Additional attached storage = storage that can be mounted to the container <br>

    Narwhal infra can have expandable main storage. <br>
    Giver infra can only have 8GB fixed main storage. <br>
    For extra storage on Giver, you can mount a disk between 1GB and 500GB..

| Infra    | Min Disk Size  | Max Disk Size  |
|:--------:|:------:|:-------:|
| Narwhal (base storage)  | 21 GB  | 200 GB  |
| Giver (additional attached storage)    | 1 GB   | 500 GB  |


| amount   | vCPU            | RAM     |
|:--------:|:---------------:|:-------:|
| very-low | 0.5 (1/2 cpu)  | 512 MB  |
| low      | 1              | 2 GB    |
| med      | 1              | 4 GB    |
| high     | 2              | 4 GB    |


<b> Examples: </b>

```toml
[sama-build]
amount = "low"
```

```toml
[sama-build]
amount = "high"
```

Manually defining the resource limits for CPU and memory (RAM):

```toml
[sama-build]
amount = "custom"
cpu = "4"
memory = "4Gi"
```

You can also set custom disk values:

!!! warning
    You cannot allocate more disk space then the max defaults allow for. <br>

```toml
[sama-build]
amount = "custom"
cpu = "2"
memory = "8Gi"
disk = "100Gi"
```

You can retain the preset defaults for CPU and memory while changing disk by: <br>

```toml
[sama-build]
amount = "med"
disk = "100Gi
```

#### pyver

This value allows you customize the version of python installed in the docker image. <br>
!!! tip
    By deafult the base image is set to use python 3.11 <br>
    `pyver = "3.11"`

If you wish to use Python 3.13 use the following setting:

```toml
[sama-build]
pyver = "3.13"
```

#### custom-image

!!! info
    This value allows you customize the base docker image. This would be used in cases where you needed to install a library/package that was not a python package (ie: aws cli, curl, etc...)

    When the `custom-image` parameter is set to `true` the system will look for the Dockerfile at the root of your python package. <b>You will need to copy the Dockerfile over to the root of your package. Modify the Dockerfile as needed. </b>

    [Link to Dockerfile](https://github.com/Samasource/soln-eng/blob/main/templates/prefect_builder/Dockerfile)
<br>

```toml
[sama-build]
custom-image = true
```

#### nps-ext

This setting allows you to use special packages/installers<br>
[Configuration details can be found here](nps_extras.md)


#### deploy-json

Configure custom deployment attributes for your flow
!!! info
    This setting will override the `deploy-list` and `deploy-num` settings <br>

    When the `deploy-json` parameter is set to `true` the system will look for a json file called `deploy.json` at the root of your python package. See below on how to generate the json file.

```toml
[sama-build]
deploy-json = true
```

!!! tip
    The only valid fields in the JSON are `name`, `schedule`, and `parameters` <br>
    The `name` field is always required <br>
    The `schedule` and `parameters` fields are optional <br>

##### Generating deploy.json with an existing deployment
!!! info
    If you setup a deployment manually with schedule or default parameters you can retrive the deploy.json by following the steps below

1. Create a file called `deploy.json` at the root of your python package
2. Navigate to the [Narwhal Gateway](https://narwhal-gateway-me3asbybaq-uc.a.run.app/api/rapidoc#get-/deploy-json)
3. Enter the `flow_name` in the appropriate field
4. Entering `deployment_name` is optional (use if you want only that specific deployment)
5. Click the `Send API Request` button
6. Copy the json from the response to the `deploy.json` file

##### Generating a deploy.json without an existing deployment
1. Create a file called `deploy.json` at the root of your python package
2. Copy the json example into the file you created in step 1
3. Modify the `name`, `schedule`, and `parameters` fields as needed

```json
{
  "deploy": [
    {
      "name": "deployment_name",
      "schedule": {
        "interval": 28800,
        "anchor_date": "2023-11-23T02:30:00+00:00",
        "timezone": "UTC"
      },
      "parameters": {
        "param": {
          "task_id": 1,
          "project_id": 10
        }
      }
    }
  ]
}
```

#### deploy-list

Set custom deployment name(s) for your flow
!!! info
    This setting will override the `deploy-num` setting <br>
    If you have multiple deployments add each name to the list <br>

```toml
[sama-build]
deploy-list = ["custom_deployment_name_1", "custom_deployment_name_2"]
```

#### deploy-num

Configure the number of deployments for your flow
!!! info
    This setting will not apply if the `deploy-list` and `deploy-json` are present <br>
    By default every flow must have at least one deployment <br>
    Example: script_name_cpp_1

```toml
[sama-build]
deploy-num = 3
```

#### infra

Customize the infrastructure where your flow will run on

!!! tip
    <b> FOR ADVANCED USERS ONLY </b> <br>
    `giver` is the specifier for Sama owned infrastructure (<b>this is the default setting</b>) <br>
    `narwhal` is the specifier for Narwhal owned infrastructure <br>
    `gke` is the specifier for Narwhal owned Google infrastructure (<b>this infra has access to GPUs</b>)

```toml
[sama-build]
infra = "narwhal"
```

#### cloud

This value allows you customize the cloud where your flow will run on <br>

!!! tip
    <b> FOR ADVANCED USERS ONLY </b> <br>
    Only available if the cloud vendor is setup to run NPS workflows

    Valid cloud vendors: <br>
    1. aws <br>
    2. gcp <br>
    3. azure

```toml
[sama-build]
infra = "azure"
```

#### region

This value allows you to change the region

!!! tip
    <b> FOR ADVANCED USERS ONLY </b> <br>
    Valid regions: <br>
    1. us <br>
    2. eu

```toml
[sama-build]
region = "eu"
```

#### skip-deploy

![depreciated](https://img.shields.io/badge/-Depreciated-red)

Skips applying the deployment to the Prefect workspace
!!! warning
    This feature is no longer supported <br>

```toml
[sama-build]
skip-deploy = true
```

#### workspace

![depreciated](https://img.shields.io/badge/-Depreciated-red)

Swap between the production and test workspaces <br>

!!! warning
    This feature is no longer supported <br>
    All flows will deployed to the production workspace

```toml
[sama-build]
workspace = "test"
```

#### pyproject.toml example

```toml
[project]
name = "narwhal"
version = "1.0.0"
description = "Add your description here"
readme = "README.md"
authors = [
    { name = "Narwhal", email = "narwhal@sama.com" }
]
requires-python = ">=3.11"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[sama-build]
amount = "med"
custom-image = true
pyver = "3.13"
```


### Examples

[Examples can be found here](nps_examples.md)
