# -*- coding: utf-8 -*-
import sys
import inspect
from typing import Union, List, Callable, Dict, Container


def is_union(tp) -> bool:
    """ Return True if a passed type is a typing.Union.

    >>> is_union(Union[int, str])
    True
    >>> is_union(str)
    False
    >>> is_union(Union)
    False
    >>> is_union(List[str])
    False
    """
    return hasattr(tp, "__origin__") and tp.__origin__ is Union


def get_union_args(tp) -> List:
    """ Return a list of typing.Union args. """
    return list(tp.__args__)


def issubclass_safe(cls, bases) -> bool:
    """ like issubclass, but return False if cls is not a class, instead of
    raising an error:

    >>> issubclass_safe(Exception, BaseException)
    True
    >>> issubclass_safe(Exception, ValueError)
    False
    >>> issubclass_safe(123, BaseException)
    False
    """
    try:
        return issubclass(cls, bases)
    except TypeError:
        return False


def get_unannotated_params(func, annotations: Container) -> List[str]:
    """ Return a list of ``func`` argument names which are not type annotated.

    ``annotations`` should be a result of get_type_hints call for ``func``.

    >>> from typing import get_type_hints
    >>> def foo(x, y: str, *, z, w: int, **kwargs): pass
    >>> annotations = get_type_hints(foo)
    >>> get_unannotated_params(foo, annotations)
    ['x', 'z']
    """
    ARGS_KWARGS = {
        inspect.Parameter.VAR_POSITIONAL,  # *args argument
        inspect.Parameter.VAR_KEYWORD      # **kwargs argument
    }
    res = []
    for name, param in inspect.signature(func).parameters.items():
        if name in annotations or param.kind in ARGS_KWARGS:
            continue
        res.append(name)
    return res


def get_globalns(func: Callable) -> Dict:
    """ Return the global namespace that will be used for the resolution
    of postponed type annotations.

    Based on ``typing.get_type_hints`` code, with a workaround for ``attrs``
    issue.
    """
    ns = dict(_get_globalns_for_attrs(func))
    ns.update(_get_globalns_as_get_type_hints(func))
    return ns


def _get_globalns_as_get_type_hints(func: Callable) -> Dict:
    """ Global namespace resolution extracted from ``get_type_hints`` method.
    Python 3.7 (https://github.com/python/cpython/blob/3.7/Lib/typing.py#L981-L988)
    Note that this is only supporting functions as input. """
    nsobj = func
    # Find globalns for the unwrapped object.
    while hasattr(nsobj, '__wrapped__'):
        nsobj = getattr(nsobj, '__wrapped__')
    return getattr(nsobj, '__globals__', {})


def _get_globalns_for_attrs(func: Callable) -> Dict:
    """ Adds partial support for postponed type annotations in attrs classes.
    Also required to support attrs classes when
    ``from __future__ import annotations`` is used (default for python 4.0).
    See https://github.com/python-attrs/attrs/issues/593 """
    if getattr(func, '__module__', None) in sys.modules:
        return dict(sys.modules[func.__module__].__dict__)
    else:
        # Theoretically this can happen if someone writes
        # a custom string to func.__module__.  In which case
        # such attrs might not be fully introspectable
        # (w.r.t. typing.get_type_hints) but will still function
        # correctly.
        return {}
