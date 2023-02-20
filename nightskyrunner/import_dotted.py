"""
Module that provides a 'get' method that returns a class or a method
based on its dotted import path.
"""

import importlib
from typing import Optional, Iterable, Callable
from .types import DottedPath

def _get_from_dotted(
        dotted_path: DottedPath
) -> Union[type,Callable]:

    # if dotted_path is only the name of the class, it is expected
    # to be in global scope
    if "." not in dotted_path:
        try:
            class_ = globals()[dotted_path]
        except KeyError:
            raise ImportError(
                f"class {dotted_path} could not be found in the global scope"
            )

    # importing the package the class belongs to
    to_import, class_name = dotted_path.rsplit(".", 1)
    try:
        imported = importlib.import_module(to_import)
    except ModuleNotFoundError as e:
        raise ImportError(
            f"failed to import {to_import} (needed to instantiate {dotted_path}): {e}"
        )

    # getting the class or method
    try:
        class_ = getattr(imported, class_name)
    except AttributeError:
        raise ImportError(
            f"class {class_name} (provided path: {dotted_path}) could not be found"
        )

    return class_
    

def get_from_dotted(
        dotted_path: DottedPath, prefixes: Optional[Iterable[str]]=None
) -> Union[type,Callable]:
    """
    Imports package.subpackage.module and returns the class or method.

    If a list of prefixes is provided, will attempt to import
    all dotted path to which the prefix is added, and returns
    the first full dotted path for which the import is successful
    (raises an ImportError if the import fails for all prefixes).

    returns:
      the class or the method

    raises:
      an ImportError if the class or any of its package / module
      could not be imported, for any reason
    """

    if prefix is None:
        return get_from_dotted(dotted_path)

    for prefix in prefixes:
        try:
            return get_from_dotted(f"{prefix}.{dotted_path}")
        except ImportError:
            pass

    prefixes_str = ", ".join([str(p) for p in prefixes])
    raise ImportError(
        f"failed to import {dotted_path} (tried with prefixes: {prefixes_str})"
    )
    
