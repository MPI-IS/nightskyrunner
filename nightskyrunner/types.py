from typing import Iterable, NewType, Any

DottedPath = NewType('DottedPath',str)
"""
The dotted path to a class or a method, e.g. "package.subpackage.module.class_name"
"""

Config = dict[str, Any | "Config"]
"""
A configuration dictionary.
"""

KwargsList = Iterable[Tuple[str,str]]
"""
Strings that can be parsed and evaluated to generate a keyword arguments
dictionary.
For example: 
"[ ['arg1', '1.0'], ['arg2', 'True']]" to be cast to:
```{'arg1':1.0, 'arg2': True} 
"""

