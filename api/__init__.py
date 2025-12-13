from .base import GameAPIAdapter, APIRegistry
from . import ps99, gag, am, bf, sab

def setup_all_adapters():
    ps99.setup()
    gag.setup()
    am.setup()
    bf.setup()
    sab.setup()

__all__ = ['GameAPIAdapter', 'APIRegistry', 'setup_all_adapters']
