# Poetry Cheat Sheet

## Creating a brand new poetry package for your script

1. Git clone the soln-eng repo onto your local machine
```bash
git clone https://github.com/Samasource/soln-eng.git
```
2. Navigate to the soln-eng repo on your local machine
3. In either the "scripts" folder or the "flows" folder type in the following command to create a new package:

```bash
poetry new <name_of_script>
```

## Poetry package structure

When you create a package using the "new" command it will contain the following files:

!!! note
    Applicable to poetry version 1.2.x and greater

```bash
.
└── wrt19_product_delivery_ptp
    ├── README.md
    ├── poetry.lock
    ├── pyproject.toml
    ├── tests
    │   └── __init__.py
    └── wrt19_product_delivery_ptp
        ├── __init__.py

```

<b> You must put your python script inside the package as shown below</b>

```bash
.
└── wrt19_product_delivery_ptp
    ├── README.md
    ├── poetry.lock
    ├── pyproject.toml
    ├── tests
    │   └── __init__.py
    └── wrt19_product_delivery_ptp
        ├── __init__.py
        └── wrt19_product_delivery_ptp.py
```

The package that gets generated when you use an older version of poetry has slightly different set of files. You can happily use your old package with a new version of poetry. Just take care to note there are a few differences with the default files that get created.

!!! note
    Applicable to poetry version 1.1.x and lower

```bash
.
├── README.rst
├── dho1_create_tasks_prp
│   ├── __init__.py
│   └── dho1_create_tasks.py
├── poetry.lock
├── pyproject.toml
└── tests
    ├── __init__.py
    └── test_dho1_create_tasks_prp.py
```

## Adding third party python packages to your script

!!! note
    For the command below to work, you must, at minimum, be in the root of the package
Navigate to the package and enter the following command:
```bash
poetry add <package_name>
```

## Updating a third party package

Poetry creates two different files to track your third party packages

<ol>
  <li>pyproject.toml --> this file stores the high level details of your project</li>
  <li>poetry.lock --> this stores a list of all the dependencies of your packages and reflects what is installed on your development environment</li>
</ol>

### Updating the pyproject.toml file

```bash
poetry add <package_name>@latest
```

<b>Note: This command will also update the poetry.lock file so you don't need to run both commands</b>

## Updating the poetry.lock file

Use this command to update all installed packages to their respective latest versions

```bash
poetry update
```

Use this command to update only the specified packages to their latest version(s)

```bash
poetry update <package_name>
```

!!! note
    This command listed above will not update the version in your pyproject.toml file

## Versioning with poetry

Please follow the following package versioning conventions

<https://py-pkgs.org/07-releasing-versioning.html>


1. Navigate to the package
2. Open your pyproject.toml file
3. Check your "version" number
4. Enter the following command to update your version:

```bash
poetry version <release_type>
```

| Release Type  |
| -------- |
| major   |
| minor   |
| patch   |

<b>WHEN YOU RELEASE YOUR CODE TO PRODUCTION IT MUST START AT VERSION 1.0.0 </b>


## Updating Poetry to a new version

```bash
poetry self update
```

## Checking the Poetry version

```bash
poetry --version
```
