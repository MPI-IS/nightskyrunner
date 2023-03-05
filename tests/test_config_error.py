"""
Testing of the classes ConfigError and ConfigErrors
"""

from nightskyrunner.config_error import ConfigError, ConfigErrors


def test_config_error():
    """
    Testing the basic functionality of ConfigError
    """
    
    error = ConfigError(name="e1")

    error.add(name="e2")
    error.add(name="e3")

    assert error.has_error()

    errors = [e[0] for e in error]
    for error_name in ("e1", "e2", "e3"):
        assert error_name in errors


def test_config_errors():
    """
    Testing the basic functionality of ConfigErrors
    """

    
    try:
        with ConfigErrors("id1"):
            ConfigErrors.add(name="e1", value=1)
            ConfigErrors.add(name="e2", value=2)
            assert ConfigErrors.has_error()
    except ConfigError:
        pass

    with ConfigErrors("id2"):
        assert not ConfigErrors.has_error()

    try:
        with ConfigErrors("id3"):
            ConfigErrors.add(name="e3", value=3)
            ConfigErrors.add(name="e4", value=4)
            assert ConfigErrors.has_error()
    except ConfigError:
        pass

    errors = ConfigErrors.errors()

    assert "id1" in errors
    assert "id2" not in errors
    assert "id3" in errors
