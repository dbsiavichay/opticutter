"""Shim de compatibilidad. ``Base`` vive ahora en ``src.shared.database``.

Se eliminará cuando los modelos importen desde ``src.shared`` (Sesión 4).
"""

from src.shared.database import Base

__all__ = ["Base"]
