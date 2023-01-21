"""
Module defining DottedPath and get_from_dotted
"""

import importlib
from typing import Callable, Iterable, NewType, Optional, Union, cast

DottedPath = NewType("DottedPath", str)
"""
The dotted path to a class or a function, e.g. "package.subpackage.module.class_name"
"""


def _get_from_dotted(dotted_path: Union[DottedPath, str]) -> Union[type, Callable]:
    # if dotted_path is only the name of the class, it is expected
    # to be in global scope
    if type(dotted_path) == type:
        return dotted_path
    if "." not in dotted_path:
        try:
            class_ = globals()[dotted_path]
        except KeyError:
            raise ImportError(
                f"class {dotted_path} could not be found in the global scope"
            )
        return class_

    # importing the package the class belongs to
    to_import, class_name = dotted_path.rsplit(".", 1)
    try:
        imported = importlib.import_module(to_import)
    except Exception as e:
        raise ImportError(
            f"failed to import {to_import} (needed to instantiate {dotted_path}): {e}"
        )

    # getting the class or function
    try:
        class_ = getattr(imported, class_name)
    except AttributeError:
        raise ImportError(
            f"class {class_name} (provided path: {dotted_path}) could not be found"
        )

    return class_


def get_from_dotted(
    dotted_path: Union[DottedPath, str], prefixes: Optional[Iterable[str]] = None
) -> Union[type, Callable]:
    """
    Imports package.subpackage.module and returns the class or function.

    If a list of prefixes is provided, will attempt to import
    all dotted path to which the prefix is added, and returns
    the first full dotted path for which the import is successful
    (raises an ImportError if the import fails for all prefixes).

    Returns:
      the class or the function

    Raises:
      an ImportError if the class or any of its package / module
      could not be imported, for any reason
    """

    if prefixes is None:
        return _get_from_dotted(dotted_path)

    for prefix in prefixes:
        try:
            dpath: DottedPath = cast(DottedPath, f"{prefix}.{dotted_path}")
            return get_from_dotted(dpath)
        except ImportError:
            pass

    prefixes_str = ", ".join([str(p) for p in prefixes])
    raise ImportError(
        f"failed to import {dotted_path} (tried with prefixes: {prefixes_str})"
    )
