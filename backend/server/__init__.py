from __future__ import annotations

from importlib import import_module

__all__ = ["app", "create_app"]


def __getattr__(name: str):
    if name in ("app", "create_app"):
        module = import_module(".app", __name__)
        return getattr(module, name)
    raise AttributeError(name)
