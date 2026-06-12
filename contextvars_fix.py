# -*- coding: utf-8 -*-
"""
Minimal contextvars implementation for SCF Python 3.9 runtime
which appears to have contextvars missing from stdlib.
Flask/Werkzeug only need ContextVar with get/set/reset.
"""
import threading
import functools

class ContextVar:
    """Minimal ContextVar compatible with Flask's usage."""
    def __init__(self, name, default=None):
        self.name = name
        self._default = default
        self._thread_local = threading.local()

    def get(self, default=...):
        try:
            return self._thread_local.value
        except AttributeError:
            if default is not ...:
                return default
            if self._default is not None:
                return self._default
            raise LookupError(f"Context variable {self.name!r} not set")

    def set(self, value):
        old = getattr(self._thread_local, 'value', _MISSING)
        self._thread_local.value = value
        return _Token(self, old)

    def reset(self, token):
        if token._var is not self:
            raise ValueError("Token from a different ContextVar")
        if token._old is _MISSING:
            try:
                del self._thread_local.value
            except AttributeError:
                pass
        else:
            self._thread_local.value = token._old


class _Token:
    __slots__ = ('_var', '_old')
    def __init__(self, var, old):
        self._var = var
        self._old = old


_MISSING = object()

# copy_context – Flask doesn't use it, provide a no-op
def copy_context():
    return {}


__all__ = ['ContextVar', 'copy_context']
