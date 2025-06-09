# Python program to check special characters
import os
import re
from pathlib import Path
from shlex import split as shlex_split
from subprocess import PIPE, check_output, run as sub_call

import flet as ft
import httpx
from google.cloud import secretmanager

GCP_PROJECT_ID = "solution-eng-345114"

SUCCESS_CODE = 0

PAKMAN_MIN_VER = {"uv": (0, 7, 6)}
PYTHON_MIN_VER = "3.11"
LICENSE_DEFAULT = "No-License"
secret_client = secretmanager.SecretManagerServiceClient()
ADMIN_OPS = False
DISABLE_SECRET = False


def run_command(command_str: str, pipe: bool = False, env_vars: dict = None) -> int:
    print(f"Running: {command_str}")

    # If env_vars is provided, update the environment with the custom variables
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)
    return (
        sub_call(shlex_split(command_str), stdout=PIPE, env=env)
        if pipe
        else sub_call(shlex_split(command_str), env=env)
    )


def download_license(pack_path: Path, license_type: str):
    print("Downloading license...")
    url = None
    if license_type == "CC-BY-NC-4.0":
        url = "https://creativecommons.org/licenses/by-nc/4.0/legalcode.txt"
    elif license_type == "Apache-2.0":
        url = "https://www.apache.org/licenses/LICENSE-2.0.txt"

    with httpx.Client() as client:
        response = client.get(url)
        if response.status_code == 200:
            # Write the response content to a file
            with open(pack_path.joinpath("LICENSE.txt"), "wb") as fd:
                fd.write(response.content)
        else:
            print(f"Error downloading license: {response.status_code}")


def run_pakman(pack_path: Path, license_type: str):
    version = None
    pakman = "uv"
    try:
        output = check_output([pakman.lower(), "--version"]).decode()
        raw_str = output.strip().split()[1]
        version = tuple(map(int, raw_str.strip().split(".")))
    except Exception as e:
        print(f"{pakman.upper()} is not installed on this system")
    if version is not None:
        if version >= PAKMAN_MIN_VER[pakman.lower()]:
            try:
                command_str = f" uv init {pack_path} --python {PYTHON_MIN_VER} --author-from auto"
                results = run_command(command_str)
                if results.returncode == SUCCESS_CODE:
                    os.chdir(pack_path)
                    run_command("uv add --dev prefect[aws]")
                    run_command(
                        "uv add libnar",
                        env_vars={
                            "UV_KEYRING_PROVIDER": "subprocess",
                            "UV_EXTRA_INDEX_URL": "https://oauth2accesstoken@us-central1-python.pkg.dev/solution-eng-345114/narwhal-pypi/simple/",
                        },
                    )

                    py_name = pack_path.name

                    uneeded_files = ["hello.py", "app.py"]
                    for ufile in uneeded_files:
                        uneeded_file = pack_path.joinpath(ufile)
                        if uneeded_file.exists() and uneeded_file.is_file():
                            uneeded_file.unlink()
                    py_file_loc = pack_path.joinpath(py_name, f"{py_name}.py")
                    # Ensure the directory exists
                    py_file_loc.parent.mkdir(parents=True, exist_ok=True)
                    py_file_loc.touch(exist_ok=True)
                    os.chdir(pack_path.parent)
                    return SUCCESS_CODE
            except Exception as e:
                print(e)
        else:
            print(f"Package manager is outdated. You need at least min version: {PAKMAN_MIN_VER}")


def list_secret():
    secret_arr = []
    secret_path = secret_client.secret_path(GCP_PROJECT_ID, "")
    parent_path = secret_path.split("/secrets", 1)[0]
    filter_str = None if ADMIN_OPS else "name:CS_"
    secret_list = secret_client.list_secrets(request={"parent": parent_path, "filter": filter_str})
    for secret in secret_list:
        secret_data = secret.name.split("/secrets/", 1)[1]
        secret_arr.append(secret_data)
    return secret_arr


def delete_secert(secret_name: str):
    secret_path = secret_client.secret_path(GCP_PROJECT_ID, secret_name)
    secret_client.delete_secret(name=secret_path)
    print(f"Deleted secret: {secret_name}")


def gen_secret(secret_name: str, secret_value: str = None, version_id: str = "latest", dd_value=None):
    try:
        secret_path_ver = secret_client.secret_version_path(GCP_PROJECT_ID, secret_name, version_id)
        secret_path = secret_client.secret_path(GCP_PROJECT_ID, secret_name)
        secret = secret_client.access_secret_version(name=secret_path_ver)
        if (secret) and (secret_value != b"" or dd_value):
            if dd_value:
                secret_value = dd_value
            secret = secret_client.add_secret_version(
                request={"parent": secret_path, "payload": {"data": secret_value}}
            )
            prev_version = int(secret.name.split("/versions/", 1)[1]) - 1
            secret_path_ver = secret_client.secret_version_path(GCP_PROJECT_ID, secret_name, prev_version)
            (
                secret_client.disable_secret_version(request={"name": secret_path_ver})
                if DISABLE_SECRET
                else secret_client.destroy_secret_version(request={"name": secret_path_ver})
            )
            print(f"Updated secret: {secret_name}")
    except Exception:
        if secret_value != b"":
            parent_path = secret_path.split("/secrets", 1)[0]
            request = secretmanager.CreateSecretRequest(
                parent=parent_path, secret_id=secret_name, secret={"replication": {"automatic": {}}}
            )
            created_secret = secret_client.create_secret(request=request)
            request = secretmanager.AddSecretVersionRequest(parent=created_secret.name, payload={"data": secret_value})
            secret = secret_client.add_secret_version(request=request)
            print(f"Created secret: {secret_name}")
        else:
            print("You cannot leave the secret value blank")


def main(page: ft.Page):
    page.title = "Multiwhal"
    page.theme_mode = ft.ThemeMode.LIGHT

    page.appbar = ft.AppBar(
        leading=ft.Icon(ft.Icons.CATCHING_POKEMON),
        leading_width=40,
        title=ft.Text("Multiwhal"),
        center_title=False,
        bgcolor=ft.Colors.BLUE,
        actions=[ft.Text("Version 3.0.0", style=ft.TextThemeStyle.HEADLINE_SMALL)],
    )

    def view_pop(view):
        page.views.pop()
        top_view = page.views[-1]
        page.go(top_view.route)

    # Open directory dialog
    def get_directory_result(e: ft.FilePickerResultEvent):
        directory_path.value = e.path or None
        directory_path.update()

    def textbox_changed(e):
        special_char = re.compile(r"[-@!#$%^&*()<>?/\|}{~:+=]")
        special_char_arr = special_char.findall(e.control.value)
        if len(special_char_arr) != 0:
            script_result_txt.value = f"The following characters are not allowed: {*special_char_arr,}"
        else:
            script_result_txt.value = None
        page.update()

    def sec_textbox_changed(e):
        if not e.control.value.startswith("CS_"):
            sec_result_txt.value = "Your secret name must start with CS_"
        else:
            sec_result_txt.value = None
        page.update()

    def pakman_cb_button_clicked(e):
        run_command("uv self update")
        run_command("uv tool install keyring --with keyrings.google-artifactregistry-auth")
        page.update()

    def run_button_clicked(e):
        if directory_path.value is None or directory_path.value == "":
            dir_path = Path.cwd()
        else:
            dir_path = directory_path.value

        if license_dd.value == "" or license_dd.value is None:
            license_type = "No-License"
        else:
            license_type = license_dd.value

        script_name = script_name_field.value
        pack_path = Path(dir_path).joinpath(script_name).resolve()

        if run_pakman(pack_path, license_type) == SUCCESS_CODE:
            if license_type != "No-License":
                download_license(pack_path, license_type)

            # create mkdocstring config
            # TODO not needed for since mkdocs not implemented for flows
            # with open(pack_path.joinpath(f"{script_name}_funcs.md"), "w") as fd:
            #     fd.write(f"::{script_name}.{script_name}\n")

            print("PACKAGE CREATION COMPLETED")
        else:
            print("Please check the terminal as an error has occurred")

        page.update()

    secret_dd = ft.Dropdown(
        label="Select Secret",
        width=500,
        options=[],
    )

    def run_secret_button_clicked(e):
        secret_name = sec_name_field.value or secret_dd.value
        value = None if "textfield" in sec_value_field.value else sec_value_field.value.encode("UTF-8")
        if ADMIN_OPS:
            gen_secret(secret_name=secret_name, secret_value=value)
        elif secret_name.startswith("CS_") or not secret_name:
            gen_secret(secret_name=secret_name, secret_value=value)

    def run_secret_list_button_clicked(e):
        secret_arr = list_secret()
        secret_dd.options = []
        for secret in secret_arr:
            secret_dd.options.append(ft.dropdown.Option(secret))
        page.update()

    def run_secret_del_button_clicked(e):
        if secret_dd.value is not None:
            delete_secert(secret_name=secret_dd.value)

    def admin_secret_op(e):
        global ADMIN_OPS
        if ADMIN_OPS:
            ADMIN_OPS = False
        else:
            ADMIN_OPS = True

    def disable_secret_op(e):
        global DISABLE_SECRET
        if DISABLE_SECRET:
            DISABLE_SECRET = False
        else:
            DISABLE_SECRET = True

    script_result_txt = ft.Text()
    script_name_field = ft.TextField(label="Enter Script Name", on_change=textbox_changed)

    sec_result_txt = ft.Text()
    sec_name_field = ft.TextField(label="Enter Secret Name", on_change=sec_textbox_changed)
    sec_value_field = ft.TextField(label="Enter Secret Value")

    get_directory_dialog = ft.FilePicker(on_result=get_directory_result)
    directory_path = ft.TextField(label=Path.cwd())

    pakman_cb_button = ft.ElevatedButton(text="Update Package Manager", on_click=pakman_cb_button_clicked, visible=True)

    # hide all dialogs in overlay
    page.overlay.extend([get_directory_dialog])

    run_button = ft.ElevatedButton(text="Run", on_click=run_button_clicked)

    secret_button = ft.ElevatedButton(text="Create Secret", on_click=run_secret_button_clicked)
    secret_list_button = ft.ElevatedButton(text="List Secrets", on_click=run_secret_list_button_clicked)
    secret_del_button = ft.ElevatedButton(text="Delete Secrets", on_click=run_secret_del_button_clicked)
    admin_secret_cb = ft.Checkbox(label=" Admin Secret Ops", value=False, on_change=admin_secret_op)
    disable_secret_cb = ft.Checkbox(label="Disable Secret", on_change=disable_secret_op)

    license_dd = ft.Dropdown(
        label="License Type",
        hint_text="Select License you wish to use for your package",
        options=[
            ft.dropdown.Option("No-License"),
            ft.dropdown.Option("Apache-2.0"),
            ft.dropdown.Option("CC-BY-NC-4.0"),
        ],
        autofocus=True,
    )

    def go_route(e):
        if int(e.data) == 0:
            page.go("/")
        else:
            page.go("/security")
        page.update()

    page.navigation_bar = ft.NavigationBar(
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.SETTINGS, label="Setup"),
            ft.NavigationBarDestination(icon=ft.Icons.SECURITY, label="Secrets"),
        ],
        on_change=go_route,
    )

    def route_change(route):
        page.views.clear()
        page.views.append(
            ft.View(
                "/",
                [
                    page.appbar,
                    page.navigation_bar,
                    script_name_field,
                    script_result_txt,
                    ft.Row(
                        [
                            ft.ElevatedButton(
                                "Package Location",
                                icon=ft.Icons.FOLDER_OPEN,
                                on_click=lambda _: get_directory_dialog.get_directory_path(
                                    initial_directory=Path.cwd()
                                ),
                                disabled=page.web,
                            ),
                            directory_path,
                        ]
                    ),
                    # license_dd,
                    ft.Row(controls=[run_button, pakman_cb_button]),
                ],
            )
        )
        if page.route == "/security":
            page.views.append(
                ft.View(
                    "/security",
                    [
                        page.appbar,
                        page.navigation_bar,
                        # admin_secret_cb,
                        sec_name_field,
                        sec_result_txt,
                        sec_value_field,
                        ft.Row([secret_button, disable_secret_cb]),
                        ft.Row([secret_list_button, secret_del_button]),
                        secret_dd,
                    ],
                )
            )
        page.update()

    page.on_route_change = route_change
    page.on_view_pop = view_pop
    page.go(page.route)


ft.app(target=main)  # , view=ft.WEB_BROWSER)
