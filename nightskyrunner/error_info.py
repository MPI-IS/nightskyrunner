"""
Module defining the get_error_info function.
"""

import os
import sys
import traceback
from typing import Optional, Tuple


def _get_package(filepath: str) -> Optional[str]:
    filepath_ = filepath.split(os.sep)
    try:
        return filepath_[-2]
    except:
        return None


def _suitable(filepath: str, filters: Tuple[str, ...]) -> bool:
    package = _get_package(filepath)
    if package is None:
        return False
    return any([f in package for f in filters])


def get_error_info(error: Exception, filters: Tuple[str, ...] = ("nightsky",)) -> str:
    """
    This function extract from the error the most information for debug,
    such as the package name, the file name and line the error occured.

    Arguments:
      error: the Exception from which information is to be extracted
      filters: package name or package substring that are more likely
        to be of interest to the developer.
    """
    _, _, exc_traceback = sys.exc_info()
    if not exc_traceback:
        return f"{type(error)}: {error}"

    traceback_details = [
        td
        for td in list(traceback.extract_tb(exc_traceback))
        if _suitable(td[0], filters)
    ]

    if not traceback_details:
        return f"{type(error)}: {error}"

    filepath, line_no, func_name, _ = traceback_details[-1]
    package = _get_package(filepath)
    filename = os.path.basename(filepath)

    if package:
        return str(
            f"{type(error).__name__}: "
            f"{str(error)} ({package}/{filename} line {line_no}, function {func_name})"
        )
    else:
        return str(
            f"{type(error).__name__}: "
            f"{str(error)} ({filename} line {line_no}, function {func_name})"
        )
