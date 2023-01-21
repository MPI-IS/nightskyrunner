"""
Module implementing functions for comparing dictionaries, lists and partial functions.
"""

from functools import partial
from typing import Any, Dict, List


def compare_partial(f1: partial, f2: partial) -> bool:
    """
    Compares two partial functions, by comparing
    their 'func', 'args' and 'keywords' arguments.
    """
    if not isinstance(f1, partial):
        return False
    if not isinstance(f2, partial):
        return False
    for attr in ("func", "args", "keywords"):
        if getattr(f1, attr) != getattr(f2, attr):
            return False
    return True


def compare_list(l1: List[Any], l2: List[Any]) -> bool:
    """
    Compares lists by comparing items at the same index.
    Returns false if the length of the two lists
    is not the same.
    Returns false if either l1 or l2 is not a list.
    This function is recursive if any element of the list is also a list.
    This function supports comparison of dictionaries and partial functions
    (see [compare_kwargs]() and [compare_partial]()).
    For other types, the default equality operator ('==') is used.
    """
    if not isinstance(l1, list):
        return False
    if not isinstance(l2, list):
        return False
    if len(l1) != len(l2):
        return False
    for v1, v2 in zip(l1, l2):
        if isinstance(v1, dict):
            if not compare_kwargs(v1, v2):
                return False
        elif isinstance(v1, list):
            if not compare_list(v1, v2):
                return False
        else:
            if isinstance(v1, partial):
                if not compare_partial(v1, v2):
                    return False
            elif v1 != v2:
                return False
    return True


def compare_kwargs(k1: Dict[str, Any], k2: Dict[str, Any]) -> bool:
    """
    Compares dictionaries.
    Returns false if the k1 or k2 is not of type
    dict.
    Returns false if k1 and k2 do not have the same keys.
    Returns false if any corresponding value is not equal.
    This function is recursive for dict values.
    This function also supports comparison
    of lists and partial functions (see [compare_list]() and [compare_partial]()).
    For other types, the default equality operation ('==') is used.
    """
    if not isinstance(k1, dict):
        return False
    if not isinstance(k2, dict):
        return False
    if len(k1) != len(k2):
        return False
    if set(k1.keys()) != set(k2.keys()):
        return False
    for key, value in k1.items():
        if isinstance(value, dict):
            same = compare_kwargs(value, k2[key])
            if not same:
                return False
        elif isinstance(value, list):
            if not compare_list(value, k2[key]):
                return False
        elif isinstance(value, partial):
            if not compare_partial(value, k2[key]):
                return False
        else:
            if not value == k2[key]:
                return False
    return True
