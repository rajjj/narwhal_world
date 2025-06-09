"""
Utilities to wrap around the standard Python json library - mostly JSON file IO

Usage examples:
    - library/nartools/tests/test_json_wrapper.py
"""

# TODO: In the future:
# - Replace `json` with alternative libs for faster performance

import json
from pathlib import Path
from typing import Any, Union

from fsspec.spec import AbstractFileSystem


def load_json_file(json_filepath: Union[str, Path], fs: AbstractFileSystem) -> Any:
    """
    Loads a specified JSON file

    Args:
        json_filepath (Union[str, Path]): The path to the JSON file that needs to be loaded
        fs (AbstractFileSystem): The filesystem under which this path exists
    """
    json_file = fs.open(json_filepath)
    json_data = json.load(json_file)
    json_file.close()
    return json_data


def write_json_file(obj: Any, json_filepath: Union[str, Path], fs: AbstractFileSystem, indent: int = 2) -> None:
    """
    Writes a JSON-serializable object to a specified destination file

    Args:
        obj (Any): The object to be dumped as JSON
        json_filepath (Union[str, Path]): The file path where the JSON data will be dumped or saved
        fs (AbstractFileSystem): The filesystem under which this path exists
        indent (int): Number of spaces to use for indentation in the output JSON file. Defaults to 2
    """
    out_file = fs.open(json_filepath, "w")
    json.dump(obj, out_file, indent=indent)
    out_file.close()


def load_json_string(json_string: str) -> Any:
    """
    Loads a JSON string into a Python object

    Args:
        json_string (str): The JSON string to be loaded

    Returns:
        The Python object corresponding to the JSON string
    """
    return json.loads(json_string)


def get_as_json_string(obj: Any, indent: int = 2) -> str:
    """
    Returns the JSON string representation of a JSON-serializable Python object

    Args:
        obj (Any): The Python object to be JSON-stringified
        indent (int): Number of spaces to use for indentation in the output JSON string. Defaults to 2

    Returns:
        The JSON string corresponding to the Python object
    """
    return json.dumps(obj, indent=indent)
