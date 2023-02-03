from pathlib import Path
from collections import Counter
from typing import Any, Type, Optional

    
    
        
# example:

config_fields = {
    'a': (is_directory(create=True), optional()),
    'b': (isint(), minmax(vmin=-1,vmax=1)),
}

class Configuration:

    def __init__(
            self,
            config_fields
    )->None:
        self._config_fields = config_fields

    def check(self, config: dict[str,Any])->None:
        for name, value in config.items():
            checks = self._config_fields[name]
            for check in checks:
                check(name,value)
            
        
