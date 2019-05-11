__version__ = '0.0.3'
VERSION = tuple(map(int, __version__.split('.')))

from .chains import C, Ops
from .response import Response, make_chainy
