from typing import NewType

ClassPath = NewType('ClassPath',str)
"""
The dotted path to a class, e.g. "package.subpackage.module.class_name"
"""


def _get_class(class_path: ClassPath) -> typing.Type:
    """
    Imports package.subpackage.module and returns the class.

    returns:
      the class

    raises:
      an ImportError if the class or any of its package / module
      could not be imported, for any reason
    """

    # if class_path is only the name of the class, it is expected
    # to be in global scope
    if "." not in class_path:
        try:
            class_ = globals()[class_path]
        except KeyError:
            raise ImportError(
                f"class {class_path} could not be found in the global scope"
            )

    # importing the package the class belongs to
    to_import, class_name = class_path.rsplit(".", 1)
    try:
        imported = importlib.import_module(to_import)
    except ModuleNotFoundError as e:
        raise ImportError(
            f"failed to import {to_import} (needed to instantiate {class_path}): {e}"
        )

    # getting the class
    try:
        class_ = getattr(imported, class_name)
    except AttributeError:
        raise ImportError(
            f"class {class_name} (provided path: {class_path}) could not be found"
        )

    return class_

{
    "PhotoTaker": {
        "description": "",
        "classpath": "",
        "configuration": {
            "classpath": "",
            "args": [],
            "kwargs": {},
            "template": {
                "field": ((method,(kwargs),)),
            }
        }
    }
}

