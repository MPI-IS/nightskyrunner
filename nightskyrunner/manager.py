from typing import NewType


"""
[Phototaker]
name = "taking pictures at night"
runner = "nightskycam.phototaker.AsiPhoto"
configuration = /opt/nightskycam/phototaker/phototaker.toml

[Ftp]
name = "uploading pictures to MPI"
runner = "nightskycam.ftp.Ftp"
configuration = /opt/nightskycam/ftp/ftp.toml
"""


"""
content of /opt/nightskycam/ftp

class = "nightskyrunner.config_getter.DynamicTomlFile",
args = ["/opt/nightskycam/ftp/config.toml"]
kwargs = {}

[template]
    modules = ["nightskyrunner.config_checkers"]
    url = {"isstr":{}}
    port = {"isint":{},is_positive:{}}
    username = {"isstr"={}}
    
    field1: {
          "minmax": {"vmin":-1, "vmax": +1},
    }


"""
