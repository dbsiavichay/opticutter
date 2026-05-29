"""Shim de compatibilidad. ``CamelModel`` vive ahora en ``src.shared.schemas``.

Se eliminará cuando los schemas importen desde ``src.shared`` (Sesión 4).
"""

from src.shared.schemas import CamelModel

__all__ = ["CamelModel"]
