"""
Module defining the ConfigError class. 
A ConfigError is to be raised when a [config.Config](Config) has unexpected key(s) or value(s)
"""


class ConfigError(Exception):
    """
    To be thrown when a [config.Config](Config)
    has unexpected key(s) or value(s)
    """

    ...
