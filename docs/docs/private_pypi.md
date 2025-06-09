# Accessing The Private Python Repo

!!! info
    Reach out to your cloud admin to be granted access to the private repo before you go any further!

## Python package manager

Install the keyring for Google to automatic authentication so you can connect to the private python repo.

#### Using UV
```bash
uv tool install keyring --with keyrings.google-artifactregistry-auth
```

#### Using Poetry
```bash
poetry self add keyrings.google-artifactregistry-auth
```

## Installing packages from the private repo

!!! warning
    You must install [Google CLoud SDK](getting_started.md#google-cloud-sdk) before proceeding!

### Authenticate to Google Cloud

!!! note
    You only have to run this command once. You are not required to re-authenticate daily.

```bash
gcloud auth login
```

### Generating the credentials file

Creates a local copy of the credentials file for use with GCP's client libraries:

!!! note
    You only have to perform this step once. <br>
    <https://cloud.google.com/docs/authentication/provide-credentials-adc#local-dev>

```bash
gcloud auth application-default login
```

### Package index config for UV
In order to download a private python package you will need to the add the following environment variables to your shell:

```bash
export UV_KEYRING_PROVIDER=subprocess
export UV_EXTRA_INDEX_URL=https://oauth2accesstoken@us-central1-python.pkg.dev/solution-eng-345114/narwhal-pypi
/simple/
```

To make this change permeant in your shell add it to your shell's rc file <br>
Using zsh:
```bash
vim ~/.zshrc
```
Then paste the above export commands into your rc file. <br>
Restart your shell or run the following command to apply the changes:
```bash
source ~/.zshrc
```


### Package index config for Poetry
You will need to the add source repo location to your pyproject.toml file. You need to do this for each Poetry package you create.

The command below auto creates the config data which tells Poetry where it should pull the package from:
```bash
poetry source add pypi
poetry source add --priority=supplemental narwhal-pypi https://us-central1-python.pkg.dev/solution-eng-345114/narwhal-pypi/simple/
```

## Publishing packages

!!! note
    This section assumes you have already created a python package and are now ready to publish it.
    <!-- <br>
    For more information see [poetry publishing documentation](https://python-poetry.org/docs/cli/#publish) -->

#### Using UV

Add the following to your pyproject.toml file:
```toml
[[tool.uv.index]]
name = "narwhal-pypi"
url = "https://oauth2accesstoken@us-central1-python.pkg.dev/solution-eng-345114/narwhal-pypi/simple/"
publish-url = "https://us-central1-python.pkg.dev/solution-eng-345114/narwhal-pypi"
```

Run the following command to build the artifacts:
```bash
uv build
```

Run the following command to publish the package:
```bash
uv publish --index narwhal-pypi --username oauth2accesstoken --keyring-provider subprocess
```

Alternatively you can set the publish url as an environment variable:

```bash
export UV_PUBLISH_URL=https://oauth2accesstoken@us-central1-python.pkg.dev/solution-eng-345114/narwhal-pypi
```

Run the following command to publish the package:
```bash
uv publish
```

#### Using Poetry

Set configure file for package index:
```bash
poetry config repositories.google "https://us-central1-python.pkg.dev/solution-eng-345114/narwhal-pypi"
```

In order to publish the package to our private python repo you will need run the following command in the root of your package:
```bash
poetry publish -r google --build
```


## FAQ

### Running into authorization issues when trying to install private packages

This problem can usually be fixed recreating Poetry's internal pyproject.toml file. Here are the steps to fix it:

1. Navigate to the poetry preferences folder (MacOS location):
```bash
cd ~/Library/Application Support/pypoetry
```
2. Remove the following files:
```bash
rm -f poetry.lock and pypoetry.toml
```
3. Re-install the google keyring:
```bash
poetry self add keyrings.google-artifactregistry-auth
```
4. Try adding the package again:
```bash
poetry add <package_name>
```
