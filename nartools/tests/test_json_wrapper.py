from pathlib import Path

from fsspec.implementations.local import LocalFileSystem
from nartools.wrappers import json as nj

TEST_OBJ = {
    "a": 1,
    "b": {
        "c": 2,
    },
}
TEST_OBJ_JSON_STRING = """{
  "a": 1,
  "b": {
    "c": 2
  }
}"""


def test_json_file_io(tmp_path):
    fs = LocalFileSystem()
    json_filepath = tmp_path / "test.json"

    nj.write_json_file(TEST_OBJ, json_filepath, fs)
    written_file_contents = fs.open(json_filepath, "r").read()
    assert written_file_contents == TEST_OBJ_JSON_STRING

    loaded_obj = nj.load_json_file(json_filepath, fs)
    assert loaded_obj == TEST_OBJ


def test_json_string_io():
    loaded_obj = nj.load_json_string(TEST_OBJ_JSON_STRING)
    assert loaded_obj == TEST_OBJ

    json_string = nj.get_as_json_string(TEST_OBJ)
    assert json_string == TEST_OBJ_JSON_STRING
