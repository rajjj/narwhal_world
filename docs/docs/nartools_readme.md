# nartools

A library that houses Narwhals' generalized solutions and tools to add a new dimension to your custom scripts ;)

## Usage

### Installation

Click [here](private_repo.md) for guidance on setting up access to the Narwhals' private PyPI repo on your system.

Once the repo is set up, you can install nartools and add it as a dependency for your Poetry package (custom solution):

```bash
poetry add nartools
```

#### Note

`nartools>=3.2.0` has `open3d` as an external dependecy, not managed by `poetry`. Before installation and usage in your solution’s Poetry package, please do the following:

1. On your local machine (so that you can test locally):

Assuming you have the base open3d packages installed on your system (this would be the case if you’ve ever run Open3D on your system), run the following in your terminal:

```bash
poetry shell  # activate your solution's venv
pip install open3d
```

2. Copy the template Dockerfile to your project and add the following lines to the custom section (so that NPS can run the code):

```docker
RUN apt install libgl1-mesa-glx libgomp1 -y
RUN pip install --upgrade pip && pip install open3d
```

Please see pyproject.toml for an up-to-date list of external dependencies. It is recommended that you list your own solution's external depedencies (e.g. open3d) in a similar way).

### Importing and using in custom scripts

Import nartools (or parts thereof) for use in your scripts, e.g.

```python
>>> from libnar import libnar
>>> narcon = libnar.Narcon()
>>> narcon.set_aws_cred()
>>> from nartools.file_manip import zero_pad_frame_nums as zpf
>>> fixer = zpf.FrameNamingFixer(
...   narcon.fs,
...   'sama-client-assets/361/testing/frame_num_padding_test/unpadded',
...   'sama-client-assets/361/testing/frame_num_padding_test/padded/',
...   'lidar_{lnum}-frame_{fnum}.pcd', 'fnum', 4
... )
>>> fixer.generate_fixed_dir()
```

The above example reads the input dir
(files: "lidar_1-frame_23.pcd", "lidar_1-frame_2.pcd", "lidar_1-frame_1023.pcd")
and produces a copy of it with the naming fixed as the output dir
(files: "lidar_1-frame_0023.pcd", "lidar_1-frame_0002.pcd", "lidar_1-frame_1023.pcd").

#### Note

The relevant AWS credentials need to have been set by the user/caller
prior to using modules from nartools

### Standalone usage on NPS web interface (Prefect flows)

[Coming soon]
Use the flows "........." on the web UI, which act as frontends to nartools modules for one-off usage without needing any coding
