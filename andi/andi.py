# -*- coding: utf-8 -*-
import typing
from collections import OrderedDict
from typing import (
    Any, Dict, List, Optional, Type, Callable, Union, Container,
    get_type_hints)

from andi.typeutils import get_union_args, is_union, get_globalns
from andi.utils import as_class_names
from andi.errors import CyclicDependencyError, NonProvidableError


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
        sel_cls = _select_type(types, can_provide)
        if sel_cls:
            result[argname] = sel_cls
    return result


Plan = typing.Dict[Type, Dict[str, Type]]


class FunctionArguments:
    """ Key marker to return the inspected function arguments into the
    ``Plan`` returned by the ``plan`` function """
    pass


def plan(class_or_func: Union[Type, Callable],
         can_provide: TypeContainerOrCallable,
         externally_provided: TypeContainerOrCallable) -> Plan:
    """ Check if it is possible to fulfill the arguments to invoke the input
    function (or to the create the input class if a class is given). If possible
    then a plan to build the requirements is returned. This plan is
    an ``OrderedDict`` containing the proper instantiation order
    for each type so that the dependencies existence is assured. The keys in
    this plan are the type, and the values are dicts where the keys are the
    params names and the values are the type required for this parameter.

    If the input is a function then there will be a final entry in the plan with
    the key ``FunctionArguments`` that contains the dictionary of the
    fulfilled arguments for this function (could be incomplete).

    This function recursively checks for dependencies. If a cyclic dependency is
    found the error ``CyclicDependencyError`` is raised.

    :param class_or_func: If a class is provided this function will create
                          a plan to fulfil its ``__init__`` method. The class
                          itself will be part of the plan in the las position.
                          If a plan for all the requirements cannot be created
                          the function will fail with ``NonProvidableError``.
                          If a method is given then this function will try
                          to create a plan to create all its arguments, but it
                          won't fail if all the required parameters cannot
                          be fulfilled. The last entry in this case will be
                          the arguments that could be fulfilled for the input
                          function with its types and the key will be
                          ``FunctionArguments``
    :param can_provide: A predicate or a dictionary that says if a class
                        is providable. Any required class found
                        by this function should be providable, otherwise,
                        ``NonProvidableError`` will be raised. There one single
                        exception for that: if a function is received as
                        input then non providable arguments
                        are allowed for the function itself. They won't be
                        in the returned plan. It is the caller responsibility
                        to deal with this case.
    :param externally_provided: A predicate or a dictionary that says if a class
                                will be provided externally.
                                The ``plan`` function won't try to resolve its
                                dependencies, so it acts as a way to stop
                                dependency injection for these classes where
                                we don't want it because they will be provided by
                                other means.
    :return: The plan ready to be used as ``build`` method input.
    """
    assert can_provide is not None
    assert externally_provided is not None
    if isinstance(can_provide, Container):
        can_provide = can_provide.__contains__
    if isinstance(externally_provided, Container):
        externally_provided = externally_provided.__contains__
    return _plan(class_or_func, can_provide, externally_provided, None)


def _plan(class_or_func: Union[Type, Callable],
          can_provide: Callable[[Optional[Type]], bool],
          externally_provided: Callable[[Optional[Type]], bool],
          dependency_stack=None) -> Plan:
    dependency_stack = dependency_stack or []
    plan_seq = OrderedDict()  # type: Plan
    type_for_arg = {}

    input_is_type = isinstance(class_or_func, type)

    if input_is_type:
        cls = typing.cast(Type, class_or_func)
        if not can_provide(cls):
            raise NonProvidableError(
                "Type {} cannot be provided".format(as_class_names(cls)))

        if externally_provided(cls):
            plan_seq[cls] = {}
            return plan_seq

        if cls in dependency_stack:
            raise CyclicDependencyError(
                "Cyclic dependency found. Dependency graph: {}".format(
                    " -> ".join(as_class_names(dependency_stack + [cls]))))
        dependency_stack = dependency_stack + [cls]
        arguments = inspect(cls.__init__)
    else:
        arguments = inspect(class_or_func)

    for argname, types in arguments.items():
        sel_cls = _select_type(types, can_provide)
        if sel_cls is not None:
            if sel_cls not in plan_seq:
                plan_seq.update(_plan(sel_cls, can_provide, externally_provided,
                                    dependency_stack))
            type_for_arg[argname] = sel_cls
        else:
            # Non fulfilling all deps is allowed for non type inputs.
            if input_is_type:
                msg = "Any of {} types are required ".format(as_class_names(types))
                msg += " in {} __init__ but none can be provided".format(
                        as_class_names(class_or_func))
                raise NonProvidableError(msg)


    plan_seq[cls if input_is_type else FunctionArguments] = type_for_arg
    return plan_seq


def build(plan: Plan, stock: Optional[Dict[Type, Any]] = None):
    """ TODO: write doc """
    stock = stock or {}
    instances = {}
    for cls, params in plan.items():
        if cls in stock:
            instances[cls] = stock[cls]
        elif cls == FunctionArguments:
            pass
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


def _select_type(types, can_provide):
    """ Choose the first type that can be provided. None otherwise. """
    sel_cls = None
    for candidate in types:
        if can_provide(candidate):
            sel_cls = candidate
            break
    return sel_cls
