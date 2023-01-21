"""
Module defining the set_logging function.
"""

import logging
from functools import partial
from pathlib import Path
from typing import List, Optional

from .status import Level, Status


def set_logging(
    stdout: bool, logfile: Optional[Path] = None, level: Level = Level.info
) -> None:
    """
    Convenience function for configuring the logging package.
    Calling this function, compared to directly configure the logging package,
    ensures all runners information will be properly logged.

    Arguments:
      stdout: if true, logs will be printed on the current terminal
      logfile: path to log file
      level: logging level
    """

    handlers: List[logging.Handler] = []

    if stdout:
        handlers.append(logging.StreamHandler())

    if logfile:
        handlers.append(logging.FileHandler(logfile))

    logging.basicConfig(level=level.value, handlers=handlers)
