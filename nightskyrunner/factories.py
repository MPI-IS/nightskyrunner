import importlib
import inspect
import toml
from pathlib import Path
from functools import partial
from typing import Optional, Iterable, Callable, Any, NewType, cast
from .config_check import ConfigTemplate, CheckerMethod
from .config_error import ConfigErrors, ConfigError
from .config_getter import ConfigGetter

DottedPath = NewType("DottedPath", str)
"""
The dotted path to a class or a function, e.g. "package.subpackage.module.class_name"
"""

ClassPath = NewType("ClassPath", str)
ModulePath = NewType("ModulePath", str)


def _get_from_dotted(dotted_path: DottedPath) -> type | Callable:

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

    # getting the class or function
    try:
        class_ = getattr(imported, class_name)
    except AttributeError:
        raise ImportError(
            f"class {class_name} (provided path: {dotted_path}) could not be found"
        )

    return class_


def get_from_dotted(
    dotted_path: DottedPath | str, prefixes: Optional[Iterable[str]] = None
) -> type | Callable:
    """
    Imports package.subpackage.module and returns the class or function.

    If a list of prefixes is provided, will attempt to import
    all dotted path to which the prefix is added, and returns
    the first full dotted path for which the import is successful
    (raises an ImportError if the import fails for all prefixes).

    returns:
      the class or the function

    raises:
      an ImportError if the class or any of its package / module
      could not be imported, for any reason
    """

    if prefixes is None:
        return get_from_dotted(dotted_path)

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


def _check_kwargs(function: Callable, kwargs: dict[str, Any]) -> None:
    """
    Raises a ConfigValueError if the keyword arguments do not
    match the function's signature.
    """
    args = inspect.getargspec(function)
    names = args[0]
    values = args[1:]
    supported = {name: value for name, value in zip(names, values)}
    nb_positional_args = len([n for n, v in supported.items() if v is None])
    if nb_positional_args != 2:
        ConfigErrors.add(
            function.__name__,
            str(kwargs),
            str(
                "configuration function checker must take 2 positional arguments "
                "(configuration field name and value)"
            ),
        )
        keyword_args = [name for name, value in supported.items() if value is not None]
        for ka in keyword_args:
            if ka not in kwargs:
                ConfigErrors.add(
                    function.__name__, ka, str("not a supported keyword argument")
                )


def _configured_check_function(
    modules: Iterable[ClassPath | ModulePath],
    function_name: str,
    kwargs=dict[str, Any],
) -> CheckerMethod:
    """
    For example:
    ```
    modules = ["nightskyrunner.configchecks", "another.module"]
    function = "minmax"
    kwargs = {"vmin":-1, "vmax": +1}
    ```
    This function imports nightskyrunner.configchecks.minmax
    (or another.module.minmax if the previous import fails)
    and checks the kwargs (vmin and vmax) match the signature
    of the function; and returns the partial function
    ```
    minmax(vmin=-1,vmax=1)
    ```
    Raises a ConfigValueError if anything goes wrong.
    """
    function: type | Callable
    try:
        if modules:
            function = get_from_dotted(function_name, prefixes=modules)
        else:
            function = get_from_dotted(function_name, prefixes=None)
    except ImportError as e:
        raise ConfigError(function_name, modules, str(e))
    _check_kwargs(function, kwargs)
    return partial(function, **kwargs)


def _field_template_config(
    modules: Iterable[ModulePath], fields: dict[str, dict[str, Any]]
) -> list[CheckerMethod]:
    """
    For example:
    ```
    modules = ["nightskyrunner.configchecks", "another.module"]
    {
      "minmax": {"vmin":-1, "vmax": +1},
      "isint": {}
    }
    ```
    returns the partial functions:
    ```
    minmax(vmin=-1, vmax=1)
    isint()
    ```
    """
    return [
        _configured_check_function(modules, field, kwargs)
        for field, kwargs in fields.items()
    ]


def _get_config_template(
    modules: Iterable[ModulePath], fields: dict[str, dict[str, dict[str, Any]]]
) -> ConfigTemplate:
    """
    For example:
    ```
    modules = ["nightskyrunner.configchecks", "another.module"]
    {
       "field1": {
          "minmax": {"vmin":-1, "vmax": +1},
          "isint": {}
       },
       "field2": {
          "isint": {}
       }
    ```
    returns the partial functions:
    ```
    {
       "field1": [minmax(vmin=-1, vmax=1),isint()],
       "field2": [isint()]
    }
    ```
    """
    r: ConfigTemplate = {}
    for field_name, checkers in fields.items():
        try:
            r[field_name] = _field_template_config(modules, checkers)
        except Exception as e:
            if type(e) == ConfigError:
                ConfigErrors.append(e)
            else:
                ConfigErrors.add(name=field_name, message=str(e))
    return r


def build_config_getter(
    class_path: DottedPath,
    args: Iterable[Any],
    kwargs: dict[str, Any],
    checkers_modules: Iterable[ModulePath],
    checkers_fields: dict[str, dict[str, dict[str, Any]]],
):
    """
    For example:
    ```
    "nightskyrunner.config_getter.DynamicTomlFile",  # dotted path to class
    ["/path/to/toml/file"],  # args to pass to class constructor
    {},  # kwargs to pass to class constructor
    # dotted path to modules with definition of config checkers functions
    modules = ["nightskyrunner.configchecks", "another.module"]
    # configuration of configuration checkers
    {
       "field1": {
          "minmax": {"vmin":-1, "vmax": +1},
       },
    }
    ```
    returns:
    ```
    DynamicTomlFile("/path/to/toml/file",**{},template={'field1':[min_max(vmin=-1,vmax=1)]})
    ```
    """

    try:
        class_ = get_from_dotted(class_path)
    except ImportError as e:
        raise ConfigError(name=class_path, message=f"failed to import: {e}")

    if not issubclass(cast(type, class_), ConfigGetter):
        raise ConfigError(
            name=class_.__name__, message="must be a subclass of ConfigGetter"
        )
    if "template" in kwargs:
        raise ConfigError(
            name=class_.__name__, message="'template' is a reserved keyword argument"
        )
    kwargs["template"] = _get_config_template(checkers_modules, checkers_fields)
    if not ConfigErrors.has_error():
        try:
            config_getter = class_(*args, **kwargs)
        except Exception as e:
            ConfigErrors.add(
                class_.__name__, f"{args}, {kwargs}", "failed to instantiate: {e}"
            )


def dict_config_getter(label: str, config: dict[str, Any]) -> ConfigGetter:

    required_keys = ("class",)

    for rk in required_keys:
        if not rk in config:
            ConfigErrors.add(
                message=f"{label}: configuration is missing the key 'class'"
            )

    accepted_keys = ("args", "kwargs", "template")
    for k in config:
        if k not in accepted_keys:
            ConfigErrors.add(message=f"{label}: unexpected key '{k}'")

    try:
        args = config["args"]
    except KeyError:
        args = []
    if type(args) != list:
        ConfigErrors.add(message=f"label/args: expected list, go {type(args)}")

    try:
        kwargs = config["kwargs"]
    except KeyError:
        kwargs = {}
    if type(args) != list:
        ConfigErrors.add(message=f"label/kwargs: expected dict, go {type(args)}")

    if "template" in config:
        tconfig = config["template"]
        try:
            checker_modules = tconfig["modules"]
        except KeyError:
            ConfigErrors.add(f"{label}/template: missing key 'template'")
        checker_fields = {
            key: value for key, value in tconfig.items() if key != "modules"
        }
        for key, value in checker_fields.items():
            if not isinstance(value, dict):
                ConfigErrors.add(
                    message=f"{label}/template/{key}: expect a dictionary, got {type(value)}"
                )

    return build_config_getter(
        config["class"], args, kwargs, checker_modules, checker_fields
    )


def toml_config_getter(filepath: Path) -> ConfigGetter:
    """
    For example:
    ```
    class = "nightskyrunner.config_getter.DynamicTomlFile",
    args = ["/path/to/toml/file"]
    kwargs = {}

    [template]
    modules = ["nightskyrunner.configchecks", "another.module"]
    field1: {
          "minmax": {"vmin":-1, "vmax": +1},
    }
    ```
    returns:
    ```
    DynamicTomlFile("/path/to/toml/file",**{},template={'field1':[min_max(vmin=-1,vmax=1)]})
    ```
    """
    if not filepath.is_file():
        raise ConfigError(f"failed to find the file {filepath}")

    try:
        content = toml.load(filepath)
    except Exception as e:
        raise ConfigError(f"failed to parse the toml file {filepath}: {e}")

    with ConfigErrors(str(filepath)):
        config_getter = dict_config_getter(str(filepath), content)
        return config_getter
