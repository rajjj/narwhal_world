# NPS Extras

## Installing the customized slam package

Install the slam package:
```bash
uv add slamus==2.0.0b6
```
!!! info
    For local testing you must first compile the slam package. To do this run the following command:

    ```bash
    uv run build-slam -f <path for compiled raccoons-slam package>
    ```

!!! tip
    If you want to vizualize your slam data when testing locally install the the `viz` extra (installs open3d):

    ```bash
    uv add slamus --extra viz
    ```

To make the slamus package work in production environments you must add the following to your `pyproject.toml` file:

```toml
[sama-build]
nps-ext = ["slam"]
```

## Testing slam locally
Once the package is compiled you will see a `raccoons-slam` folder in the path you specified. Use the compiled package and follow the example specified in the [raccoons slam repo](https://github.com/Samasource/raccoons-slam).
