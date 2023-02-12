"""
Module defining the Config type
"""

from typing import Any

Config = dict[str, Any | "Config"]
"""
A configuration dictionary.
"""
