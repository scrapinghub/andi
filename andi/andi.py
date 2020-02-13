# -*- coding: utf-8 -*-
import sys
import types
from typing import (
    Dict, List, Optional, Type, Callable, Union, Container,
    get_type_hints,
)

from andi.typeutils import get_union_args, is_union


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


def _get_globalns(func: Callable) -> Dict:
    """ Returns the global namespace that will be used for the resolution
    of postponed type annotations """
    ns = dict(_get_globalns_for_attrs(func))
    ns.update(_get_globalns_as_get_type_hints(func))
    return ns


def inspect(func: Callable) -> Dict[str, List[Optional[Type]]]:
    """
    For each argument of the ``func`` return a list of possible types.
    """
    globalns = _get_globalns(func)
    annotations = get_type_hints(func, globalns)
    annotations.pop('return', None)
    annotations.pop('cls', None)  # FIXME: pop first argument of methods
    res = {}
    for key, tp in annotations.items():
        if is_union(tp):
            res[key] = get_union_args(tp)
        else:
            res[key] = [tp]
    return res


def to_provide(
        arguments_or_func: Union[
            Callable,
            Dict[str, List[Optional[Type]]]
        ],
        can_provide: Union[
            Container[Type],
            Callable[[Optional[Type]], bool]
        ]
        ) -> Dict[str, Optional[Type]]:
    """
    Return a dictionary ``{argument_name: type}`` with types which should
    be provided.

    ``arguments_or_func`` should be either a callable, or
    a result of andi.inspect call for a callable.

    ``can_provide`` can be either a function which receives a type and
    returns True if argument of such type can be provided, or a container
    (e.g. a set) with supported types.
    """
    if callable(arguments_or_func):
        arguments = inspect(arguments_or_func)
    else:
        arguments = arguments_or_func

    if isinstance(can_provide, Container):
        can_provide = can_provide.__contains__

    result = {}
    for argname, types in arguments.items():
        for cls in types:
            if can_provide(cls):
                result[argname] = cls
                break
    return result
