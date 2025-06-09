"""
Module to hold some convenient Python dictionary manipulation functions
"""


from typing import Any, List


def dict_get(dic: dict, key_seq: List[str]) -> Any:
    """
    Gets the value at a specified path of keys in a dictionary, or None if the path does not exist
    E.g. dic = {'a': {'b': {'c': 1}}}, key_seq = ['a', 'b']; returns: {'c': 1}

    Args:
        dic (dict): A dictionary object that contains key-value pairs
        key_seq (List[str]): A list of strings representing a sequence of keys in a nested dictionary
    """
    dic_copy = dic
    for key in key_seq[:-1]:
        val = dic_copy.get(key)
        if type(val) == dict:
            dic_copy = val
        else:
            return None
    return dic_copy.get(key_seq[-1])


def set_dict_val(dic: dict, key_seq: List[str], val: Any) -> None:
    """
    Sets the value at a specified path of keys in a dictionary recursively, i.e., creating child dictionaries if they don't exist

    Args:
        dic (dict): A dictionary that we want to modify
        key_seq (List[str]): A list of strings representing a sequence of keys in a nested dictionary
        val (Any): The value that we want to set in the dictionary at the specified key sequence
    """
    if len(key_seq) == 1:
        dic[key_seq[0]] = val
        return
    if key_seq[0] not in dic.keys() or type(dic[key_seq[0]]) is not dict:
        dic[key_seq[0]] = {}
    set_dict_val(dic[key_seq[0]], key_seq[1:], val)
