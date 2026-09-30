__version__ = "0.1.0"

from .api import compile_source
from . import binfmt
from .dispatcher import Dispatch

__all__ = ["compile_source", "binfmt", "Dispatch", "__version__"]
