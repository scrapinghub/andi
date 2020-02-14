# -*- coding: utf-8 -*-
import sys
from typing import Union, List, Callable, Dict


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
    """ Return a list of typing.Union args.
    NoneType objects are converted to None for simplicity.
    """
    return _none_type_to_none(tp.__args__)


def _none_type_to_none(lst):
    return [(el if el is not None.__class__ else None) for el in lst]


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
    if func.__module__ in sys.modules:
        return dict(sys.modules[func.__module__].__dict__)
    else:
        # Theoretically this can happen if someone writes
        # a custom string to func.__module__.  In which case
        # such attrs might not be fully introspectable
        # (w.r.t. typing.get_type_hints) but will still function
        # correctly.
        return {}
