"""cmake2doc: documentation generator for CMake.

Kept free of the tree-sitter import so that the pure-Python parts of the
package can be imported (and tested) on their own.
"""

from .errors import Cmake2mdError
from .errors import ParseError
from .errors import UsageError

__version__ = '0.1.0'

__all__ = [
    'Cmake2mdError',
    'ParseError',
    'UsageError',
    '__version__',
]
