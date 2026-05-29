"""Shim de compatibilidad. La config vive ahora en ``src.shared.config``.

Se eliminará cuando todos los módulos importen desde ``src.shared`` (Sesión 4).
"""

from src.shared.config import Config, config

__all__ = ["Config", "config"]
