"""
Unit tests for the configcheck module
"""

from nightskyrunner import configcheck


def test_configuration_value_error():
    """
    Test the class ConfigurationValueError
    """
    error1 = configcheck.ConfigurationValueError("error1", 1, "error message 1")
    error2 = configcheck.ConfigurationValueError("error2", 2, "error message 2")

    error1.add(error2)

    for index,(error, value, message) in enumerate(error1):
        assert error == f"error{index+1}"
        assert value == index+1
        assert message == f"error message {index}"

