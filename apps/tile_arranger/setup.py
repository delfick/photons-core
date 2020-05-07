from tile_arranger import VERSION

from setuptools import setup, find_packages

# fmt: off

setup(
      name = "lifx-photons-tile-arranger"
    , version = VERSION
    , packages = find_packages(include="tile_arranger.*", exclude=["tests*"])
    , include_package_data = True

    , python_requires = ">= 3.6"

    , install_requires =
      [ "delfick_project==0.7.4"
      , "lifx-photons-core>=0.25.0"
      , "tornado==5.1.1"
      , "whirlwind-web==0.9.0"
      ]

    , extras_require =
      { "tests":
        [ "noseOfYeti==2.0.0"
        , "asynctest==0.12.2"
        , "pytest==5.3.1"
        , "alt-pytest-asyncio==0.5.1"
        ]
      }

    , entry_points =
      { 'console_scripts' :
        [ 'run_tile_arranger_pytest = tile_arranger:run_pytest'
        ]
      , "lifx.photons": ["tile_arranger = tile_arranger.addon"]
      }

    # metadata for upload to PyPI
    , url = "http://github.com/delfick/photons-core"
    , author = "Stephen Moore"
    , author_email = "delfick755@gmail.com"
    , description = "A server for interacting with LIFX lights over the LAN"
    , license = "MIT"
    , keywords = "lifx photons tiles"
    , long_description = open("README.rst").read()
    )

# fmt: on
