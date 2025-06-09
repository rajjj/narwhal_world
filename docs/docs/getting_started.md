# Getting Started Guide

!!! note
    The guide assumes you have a Mac, <b>Windows machines are not supported!</b>


## Visual Studio Code
Visual Studio Code is the default IDE for the Narwhals team.

Install VSCode: <br>
<https://code.visualstudio.com/download>

Configuring VSCode: <br>
<https://samasource.atlassian.net/wiki/spaces/SES/pages/31170157/Configuring+Visual+Studio+Code>

## Homebrew
Homebrew is a package manager commonly used on MacOS

[Install Hombrew](https://brew.sh/)

After Hombrew is installed run the following command:
```bash
brew analytics off
```

## Git Setup

Verify that git is installed on your machine:
```bash
git --version
```

If git is not present install it using the following command:
```bash
brew install git
```

### Git Profile Setup


#### Git Config

Open the terminal and enter the following: <br>

```bash
git config --global user.name "<your-username>"
git config --global user.email "<your-email-address>"
```

Replace `user.name` with your github username <br>
Replace `user.email` with the email associated with your github account

!!! warning
    Incorrectly setting up these fields will create errors during commit/pull operations


#### Authenticating to Github

Install the github utility:
```bash
brew install gh
```

Open the terminal and enter the following:
```bash
gh auth login
```

Select the following options (follow the terminal prompts):
```bash linenums="1"
Github.com
HTTPS
Login with a web browser
```
## Python

Python is the only language the Narwhals team uses. Currently only two versions of python are supported

!!! warning
    <b>Python 3.9 is being depreciated switch to 3.11 </b>

| Version  |
| -------- |
| 3.11.x    |
| 3.13.x   |

Check you have the correct version installed:
```bash
python --version
```
### Installing Python

Listed below are a few different ways to download and install Python onto your machine. <br>
Pick the solution you find the easiest to use.

#### Installing via the offical package

Download the installer directly from the python offical website:<br>
<https://www.python.org/downloads/>


#### Installing via homebrew
```bash
brew install python@3.11
```
To install python 3.9 enter the following command:
```bash
brew install python@3.9
```

#### Installing via pyenv

!!! warning
    <b>FOR ADVANCED USERS </b> <br>
    [pyenv](https://github.com/pyenv/pyenv) allows you to more easily switch between different versions of python.

Install pyenv via homebrew:
```bash
brew install pyenv
```

Install the all required versions of python using pyenv:

```bash
pyenv install 3.9
```
```bash
pyenv install 3.11
```
Set your global python version:
```bash
pyenv global 3.11
```

## Pre-commit

Pre-commit is used to run checks on files in the `soln-eng` repo. <br>
See the [pre-commit homepage](https://pre-commit.com/) for more information.

### Installing Pre-commit

Open a terminal and type:
```bash
brew install pre-commit
```
### Enabling Pre-commit
In the root of the soln-eng repo run the following command:
```bash
pre-commit install
```

## Python Package Manager


### Installing UV

 For the most up-to-date instructions see UV's offical docs: <br>
<https://docs.astral.sh/uv/getting-started/installation>

<b> Note: If you are having problems with the official installer you can use homebrew to install it </b>
```bash
brew install uv
```

### Updating UV

```bash
uv self update
```

### Checking UV version
```bash
uv --version
```
!!! warning
    <b>Poetry is being depreciated in favour of UV</b>


### Installing Poetry

For the most up-to-date instructions see Poetry's offical docs: <br>
<https://python-poetry.org/docs/>

Poetry recommended install command: <br>
```bash
curl -sSL https://install.python-poetry.org | python3
```

Poetry export path command will look similar to the following:

!!! tip
    During installation Poetry will display the command to set your environment.
    The command will have a format like:
    ```bash
    export PATH="/<path_to_home_profile>/.local/bin:$PATH"
    ```

<b> Note: If you are having problems with the official installer you can use homebrew to install it </b>
```bash
brew install poetry
```

### Updating Poetry

```bash
poetry self update
```

### Poetry Configuration
To create a virtual environments in the project directory run the following command:
```bash
poetry config virtualenvs.in-project true
```

### Checking Poetry version
```bash
poetry --version
```

## Google Cloud SDK

The Google Cloud SDK is needed to access private pypi repo and other Google services

!!! note
    If you are looking to access the private pypi repo see [Private python repo](private_repo.md) for more details


Check if the gcloud sdk is installed:
```bash
gcloud --version
```

Install the sdk if it is missing from your machine:
```bash
brew install --cask google-cloud-sdk
```

Add the gcloud path after installing the sdk:

default zsh command (MacOS default):

```bash
source "/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.zsh.inc"
```

<b> Note: Only run the below command if you are using a bash terminal </b>
```bash
source "/opt/homebrew/Caskroom/google-cloud-sdk/latest/google-cloud-sdk/path.bash.inc"
```

## Docker Desktop

Used to run/interact with docker containers.

Download here:
<https://www.docker.com/products/docker-desktop/>


## AWS CLI

The AWS CLI is optional, you do not need to install it if you do not plan on using it.

```bash
brew install awscli
```
