"""Browser automation backends."""

from .base import BrowserBackend
from .cdp_backend import CDPBackend
from .playwright_backend import PlaywrightBackend

__all__ = ["BrowserBackend", "CDPBackend", "PlaywrightBackend"]
