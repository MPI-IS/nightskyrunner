import toml
from pathlib import Path
from .config import Config
from .configcheck import ConfigurationValueError, ConfigTemplate, check_configuration


class ConfigGetter:

    def __init__(
            self,
            template: Optional[ConfigTemplate]=None,
            override: Optional[Config] = None
    )->None:
        self._template = template
        self._override = override
    
    def _get(self)->configcheck.Config:
        raise NotImplementedError()

    def get(self)->Config:
        config = self._get()
        if self._override is not None:
            for key, value in self._override.items():
                config[key]=value
        if self._template is not None:
            check_configuration(template, config)
        return config


def StaticTomlFile(ConfigGetter):
    def __init__(
            self,
            path: str | Path,
            template: Optional[ConfigTemplate]=None,
            override: Optional[Config] = None
    )->None:
        super().__init__(template=template, override=override)
        if isinstance(path,str):
            path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"failed to find configuration file {path}"
            )
        self._path = path
        self._config: Config = toml.loads(path.read_text())

    def _get(self)->Config:
        return self._config

    
def DynamicTomlFile(ConfigGetter):
    def __init__(
            self,
            path: str | Path,
            template: Optional[ConfigTemplate]=None,
            override: Optional[Config] = None
    )->None:
        super().__init__(template=template, override=override)
        if isinstance(path,str):
            path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(
                f"failed to find configuration file {path}"
            )
        self._path = path
    
    def get(self)->Config:
        self._config: Config = toml.loads(path.read_text())
