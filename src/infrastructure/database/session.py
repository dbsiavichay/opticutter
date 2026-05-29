"""Shim de compatibilidad. La sesión vive ahora en ``src.shared.database``.

Se eliminará cuando todo importe desde ``src.shared`` (Sesión 4).
"""

from src.shared.database import SessionLocal, engine, get_db

__all__ = ["SessionLocal", "engine", "get_db"]
