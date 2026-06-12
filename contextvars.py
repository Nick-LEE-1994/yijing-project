# -*- coding: utf-8 -*-
"""
contextvars – 最小实现 (Python 3.7–3.9 标准库兼容)
提供 Flask / Werkzeug 所需的 ContextVar 接口。
SCF Python 3.9 运行时在标准库中似乎缺少此模块，故此提供。
"""
import threading

__all__ = ["ContextVar", "copy_context"]

_MISSING = object()


class ContextVar:
    """最小化的 ContextVar，使用 threading.local() 实现。"""

    def __init__(self, name, default=...):
        self.name = name
        self._default = default
        self._local = threading.local()

    def get(self, default=...):
        try:
            return self._local.value
        except AttributeError:
            if default is not ...:
                return default
            if self._default is not ...:
                return self._default
            raise LookupError(f"Context variable {self.name!r} not set")

    def set(self, value):
        old = getattr(self._local, "value", _MISSING)
        self._local.value = value
        return _Token(self, old)

    def reset(self, token):
        if not isinstance(token, _Token) or token._var is not self:
            raise ValueError("Token from a different ContextVar")
        if token._old is _MISSING:
            try:
                del self._local.value
            except AttributeError:
                pass
        else:
            self._local.value = token._old


class _Token:
    __slots__ = ("_var", "_old")
    def __init__(self, var, old):
        self._var = var
        self._old = old


def copy_context():
    """Flask 未使用此方法，保留占位。"""
    return {}
