# -*- coding: utf-8 -*-
from typing import (
    Dict, List, Optional, Type, Callable, Union, Container,
    get_type_hints,
)

from andi.typeutils import get_union_args, is_union, get_globalns


def inspect(func: Callable) -> Dict[str, List[Optional[Type]]]:
    """
    For each argument of the ``func`` return a list of possible types.
    """
    globalns = get_globalns(func)
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
