from typing import Iterable, NewType, Any


Config = dict[str, Any | "Config"]
"""
A configuration dictionary.
"""

KwargsList = Iterable[Tuple[str, str]]
"""
Strings that can be parsed and evaluated to generate a keyword arguments
dictionary.
For example: 
"[ ['arg1', '1.0'], ['arg2', 'True']]" to be cast to:
```{'arg1':1.0, 'arg2': True} 
"""
