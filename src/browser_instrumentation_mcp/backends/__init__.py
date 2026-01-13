"""Browser automation backends."""

from .base import BrowserBackend
from .playwright_backend import PlaywrightBackend

__all__ = ["BrowserBackend", "PlaywrightBackend"]
