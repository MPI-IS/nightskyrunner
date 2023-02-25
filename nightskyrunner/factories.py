import importlib
from functools import partial
from typing import Optional, Iterable, Callable
from .types import DottedPath


DottedPath = NewType('DottedPath',str)
"""
The dotted path to a class or a method, e.g. "package.subpackage.module.class_name"
"""


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




def _check_kwargs(method: Callable, kwargs: dict[str,Any])->None:
    """
    Raises a ConfigValueError if the keyword arguments do not
    match the method's signature.
    """
    with config_value_error() as error:
        args = inspect.getargspec(method)
        names = args[0]
        values = args[1:]
        supported = {name:value for name, value in zip(names,values)}
        nb_positional_args = len([n for n,v in supported.items() if v is None])
        if nb_positional_args != 2:
            error.add(
                ConfigValueError(
                    method.__name__, str(kwargs),
                    str(
                        "configuration method checker must take 2 positional arguments ",
                        "(configuration field name and value)"
                    )
                )
            )
            keyword_args = [name for name,value in supported.items() if value is not None]
                for ka in keyword_args:
            if ka not in kwargs:
                error.add(
                    ConfigValueError(
                        method.__name__, ka, str("not a supported keyword argument")
                    )
                )
            
    

def _configured_check_method(
            modules: Iterable[ClassPath],
            method: str,
            kwargs = dict[str,Any],
)->Callable[[],bool]:
    """
    For example:
    ```
    modules = ["nightskyrunner.configchecks", "another.module"]
    method = "minmax"
    kwargs = {"vmin":-1, "vmax": +1}
    ```
    This method imports nightskyrunner.configchecks.minmax 
    (or another.module.minmax if the previous import fails)
    and checks the kwargs (vmin and vmax) match the signature
    of the method; and returns the partial method 
    ```
    minmax(vmin=-1,vmax=1)
    ```
    Raises a ConfigValueError if anything goes wrong.
    """
    method: Union[type,Callable]
    try:
        if modules:
            method = get_from_dotted(method,prefixes=modules)
        else:
            method = get_from_dotted(method,prefixes=None)
    except ImportError as e:
        raise ConfigValueError(
            method, modules, str(e)
        )
    _check_kwargs(method, kwargs)
    return partial(method,**kwargs)
    

def _field_template_config(
        modules: Iterable[ModulePath],
        fields: dict[str,dict[str,Any]]
)->list[Callable[[],bool]]
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
        _configured_check_method(
            modules, field, kwargs
        ) for field,kwargs in fields.items()
    ]


def _get_config_template(
            modules: Iterable[ModulePath],
            fields: dict[str,dict[str,dict[str,Any]]]
)-> ConfigTemplate:
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
    return {
        field_name: _field_template_config(modules,checkers)
        for field_name, checkers in fields.items()
    }
    

def build_config_getter(
            class_path: DottedPath,
            args: Iterable[Any],
            kwargs: dict[str,Any],
            checkers_modules: Iterable[ModulePath],
            checkers_fields: dict[str,dict[str,dict[str,Any]]]
)
    """
    For example:
    ```
    "nightskyrunner.config_getter.DynamicTomlFile",  # dotted path to class
    ["/path/to/toml/file"],  # args to pass to class constructor
    {},  # kwargs to pass to class constructor
    # dotted path to modules with definition of config checkers methods
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
    def __init__(
            self,
            class_path: DottedPath,
            args: Iterable[Any],
            kwargs: dict[str,Any],
            checkers_modules: Iterable[ModulePath],
            checkers_fields: dict[str,dict[str,dict[str,Any]]]
    )->None:
        try:
            class_ = get_from_dotted(class_path)
        except ImportError as e:
            raise ConfigValueError(
                "ConfigGetter", class_path, f"failed to import: {e}"
            )
        if not issubclass(class_,ConfigGetter):
            raise ConfigValueError(
                "ConfigGetter",class_.__name__,"must be a subclass of ConfigGetter"
            )
        if 'template' in kwargs:
            raise ConfigValueError(
                class_.__name__,'template',"'template' is a reserved keyword argument"
            )
        kwargs['template'] =  _get_config_template(
            checkers_modules, checkers_fields
        )
        try:
            self.config_getter = class_(*args,**kwargs)
        except Exception as e:
            ConfigErrors.add(
                class_.__name__,
                f"{args}, {kwargs}",
                "failed to instantiate: {e}"
            )
            
def dict_config_getter(label: str, config: dict[str,Any])->ConfigGetter:

    required_keys = ('class',)

    for rk in required_keys:
        if not rk in config:
            ConfigErrors.add(
                message=f"{label}: configuration is missing the key 'class'"
            )

    accepted_keys = ('args','kwargs','template')
    for k in config:
        if k not in accepted_keys:
            ConfigErrors.add(
                message=f"{label}: unexpected key '{k}'"
            )

    try:
        args = k['args']
    except KeyError:
        args = []
    if type(args)!=list:
        ConfigErrors.add(message=f"label/args: expected list, go {type(args)}")
        
    try:
        kwargs = k['kwargs']
    except KeyError:
        kwargs = {}
    if type(args)!=list:
        ConfigErrors.add(message=f"label/kwargs: expected dict, go {type(args)}")
        
    if 'template' in config:
        tconfig = config['template']
        try:
            checker_moduels = tconfig['modules']
        except KeyError:
            ConfigErrors.add(
                f"{label}/template: missing key 'template'"
            )
        checker_fields = {
            key:value for key,value in tconfig.items()
            if key != 'modules'
        }
        for key,value in checker_fields.items():
            if not isinstance(value,dict):
                ConfigErrors.add(
                    message=f"{label}/template/{key}: expect a dictionary, got {type(value)}"
                )

    return build_config_getter(
        config['class'],
        args, kwargs,
        checkers_modules, checkers_fields
    )
        
def toml_config_getter(filepath: Path)->ConfigGetter:
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
    if not content.is_file():
        raise ConfigError(
            f"failed to find the file {filepath}"
        )
    
    try:
        content = toml.load(content)
    except Exception as e:
        raise ConfigError(
            f"failed to parse the toml file {filepath}: {e}"
    )

    with ConfigErrors(str(filepath)):
        config_getter =  dict_config_getter(str(filepath),content)
        return config_getter
)
