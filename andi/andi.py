# -*- coding: utf-8 -*-
import typing
from collections import OrderedDict
from typing import (
    Any, Dict, List, Optional, Type, Callable, Union, Container,
    get_type_hints)

from andi.typeutils import get_union_args, is_union, get_globalns
from andi.utils import as_class_names


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


TypeContainerOrCallable = Union[
    Container[Type],
    Callable[[Optional[Type]], bool]
]


def to_provide(
        arguments_or_func: Union[
            Callable,
            Dict[str, List[Optional[Type]]]
        ],
        can_provide: TypeContainerOrCallable
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


Plan = typing.Dict[Type, Dict[str, Type]]


class NonProvidableError(TypeError):
    """ Raised when a type is not providable """


class CyclicDependencyError(TypeError):
    """ Raised on cyclic dependencies """


def plan(arguments_or_class: Union[
            Type,
            Dict[str, List[Optional[Type]]]
         ],
         can_provide: TypeContainerOrCallable,
         externally_provided: TypeContainerOrCallable) -> Plan:
    """ TODO: Here the docstring """
    assert can_provide is not None
    assert externally_provided is not None
    if isinstance(can_provide, Container):
        can_provide = can_provide.__contains__
    if isinstance(externally_provided, Container):
        externally_provided = externally_provided.__contains__
    return _plan(arguments_or_class, can_provide, externally_provided, None)


def _plan(arguments_or_class: Union[
            Type,
            Dict[str, List[Optional[Type]]]
          ],
          can_provide: Callable[[Optional[Type]], bool],
          externally_provided: Callable[[Optional[Type]], bool],
          dependency_stack=None) -> Plan:
    dependency_stack = dependency_stack or []
    tasks = OrderedDict()  # type: Plan
    type_for_arg = {}

    input_is_type = isinstance(arguments_or_class, type)

    if input_is_type:
        cls = typing.cast(Type, arguments_or_class)
        if not can_provide(cls):
            raise NonProvidableError(
                "Type {} cannot be provided".format(as_class_names(cls)))

        if externally_provided(cls):
            tasks[cls] = {}
            return tasks

        if cls in dependency_stack:
            raise CyclicDependencyError(
                "Cyclic dependency found. Dependency graph: {}".format(
                    " -> ".join(as_class_names(dependency_stack + [cls]))))
        dependency_stack = dependency_stack + [cls]
        params_list = inspect(cls.__init__)
    else:
        params_list = typing.cast(Dict[str, List[Optional[Type]]], arguments_or_class)

    for argname, types in params_list.items():
        sel_cls = select_type(types, can_provide)
        if sel_cls:
            if sel_cls not in tasks:
                tasks.update((_plan(sel_cls, can_provide, externally_provided,
                                    dependency_stack)))
        else:
            msg = "Any of {} types are required ".format(as_class_names(types))
            if input_is_type:
                msg += "in {} __init__ but none can be provided".format(
                    as_class_names(arguments_or_class))
            else:
                msg += "for the argument {} but none can be provided".format(argname)
            raise NonProvidableError(msg)
        type_for_arg[argname] = sel_cls

    if input_is_type:
        tasks[cls] = type_for_arg
    return tasks


def select_type(types, can_provide):
    sel_cls = None
    for candidate in types:
        if can_provide(candidate):
            sel_cls = candidate
            break
    return sel_cls


def build(plan: Plan, stock: Optional[Dict[Type, Any]] = None):
    stock = stock or {}
    instances = {}
    for cls, params in plan.items():
        if cls in stock:
            instances[cls] = stock[cls]
        else:
            kwargs = {param: instances[pcls]
                      for param, pcls in params.items()}
            instances[cls] = cls(**kwargs)
    return instances


def plan_str(plan: Plan):
    str_dict = {}
    for cls, params in plan.items():
        str_dict[cls.__name__] = {p: c.__name__ for p, c in params.items()}
    return "\n".join(map(str, str_dict.items()))
