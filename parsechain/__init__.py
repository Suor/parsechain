__version__ = '0.0.1'
VERSION = tuple(map(int, __version__.split('.')))

from chains import C
from response import Response, make_chainy
