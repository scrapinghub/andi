# -*- coding: utf-8 -*-
from collections import OrderedDict
from typing import (
    Dict, List, Optional, Type, Callable, Union, Container,
    get_type_hints, Tuple, cast)

from andi.typeutils import (
    get_union_args,
    is_union,
    get_globalns,
    get_unannotated_params,
)
from andi.errors import CyclicDependencyError, NonProvidableError


def inspect(func: Callable) -> Dict[str, List[Optional[Type]]]:
    """
    For each argument of the ``func`` return a list of possible types.
    Non annotated arguments are also returned with an empty list of possible
    types.
    """
    globalns = get_globalns(func)
    annotations = get_type_hints(func, globalns)
    for name in get_unannotated_params(func, annotations):
        annotations[name] = None
    annotations.pop('return', None)
    annotations.pop('self', None)  # FIXME: pop first argument of methods
    annotations.pop('cls', None)
    res = {}
    for key, tp in annotations.items():
        if is_union(tp):
            res[key] = get_union_args(tp)
        else:
            res[key] = [] if tp is None else [tp]
    return res


TypeContainerOrCallable = Union[
    Container[Type],
    Callable[[Type], bool]
]


def to_provide(
        arguments_or_func: Union[
            Callable,
            Dict[str, List[Optional[Type]]]
        ],
        is_injectable: TypeContainerOrCallable
        ) -> Dict[str, Optional[Type]]:
    """
    Return a dictionary ``{argument_name: type}`` with types which should
    be provided.

    ``arguments_or_func`` should be either a callable, or
    a result of andi.inspect call for a callable.

    ``is_injectable`` can be either a function which receives a type and
    returns True if argument of such type can be provided, or a container
    (e.g. a set) with supported types.
    """
    if callable(arguments_or_func):
        arguments = inspect(arguments_or_func)
    else:
        arguments = arguments_or_func

    is_injectable, externally_provided = _ensure_input_type_checks_as_func(
        is_injectable, [])

    result = {}
    for argname, types in arguments.items():
        sel_cls = _select_type(types, is_injectable, externally_provided)
        if sel_cls:
            result[argname] = sel_cls
    return result


Plan = Dict[Type, Dict[str, Type]]


def plan_for_func(func: Callable, *,
                  is_injectable: TypeContainerOrCallable,
                  externally_provided: Optional[TypeContainerOrCallable] = None,
                  strict=False) -> Tuple[Plan, Dict[str, Type]]:
    """ Plan the sequence of instantiation tasks required to fulfill the
    the arguments of the given function (dependency injection).

    The plan is a sequence encoded in a ``OrderedDict``. Each task in the plan
    contains:

    * A key, with the class that must be built in this task
    * The value, which a dictionary with all the kwargs required for the
      key ``__init__`` method. This dictionary has argument names as keys
      and classes (types) as values.

    The best way to understand a plan is to see how a typical building
    function would use it to build the instances::

        def build(plan):  # Build all the instances from a plan
            instances = {}
            for cls, args in plan.items():
                kwargs = {arg: instances[arg_cls]
                          for arg, arg_cls in args.items()}
                instances[cls] = cls(**kwargs)
            return instances

    Note that the generated instances dictionary would contain not only the
    dependencies for the function given as argument, but also all the
    dependencies of the dependencies. In other words, the plan function
    is able to plan the whole tree of dependencies.

    This function returns a second dictionary (argument_name -> type) with
    the input function arguments for which it was possible to create a plan.
    This way the function could be invoked with the following code::

        plan, fulfilled_args = plan_for_func(func, ...)
        instances = build(plan)
        kwargs = {arg: instances[arg_cls]
                  for arg, arg_cls in fulfilled_args.items()}
        func(
            other_arg='value, # argument that is out of the scope of dependency injection
            **kwargs,
        )

    If the argument ``strict`` is True then this function will fail
    with ``NonProvidableError`` if not all the required arguments
    for the input function can be resolved. When ``strict`` is False, this
    function provides the plan only for those arguments that could be resolved.

    This function recursively checks for dependencies. If a cyclic dependency
    is found, ``CyclicDependencyError`` is raised.

    Any type found in the dependency tree that is injectable can as well
    has its own dependencies. If the planner fails to fulfill any of this
    dependencies, ``NonProvidableError`` is raised, regardless of a value
    of ``strict`` argument (even if strict=False).

    See a full example in the following doctest:

    >>> class A:
    ...     value = 'a'
    ...
    >>> class B:
    ...     def __init__(self, a: A):
    ...         self.a = a
    ...         self.value = 'b'
    ...
    >>> def fn(a: A, b: B, non_annotated):
    ...     assert b.a is a
    ...     return 'Called with {}, {}, {}'.format(a.value, b.value, non_annotated)
    ...
    >>> def build(plan):  # Build all the instances from a plan
    ...     instances = {}
    ...     for cls, args in plan.items():
    ...         kwargs = {arg: instances[arg_cls]
    ...                   for arg, arg_cls in args.items()}
    ...         instances[cls] = cls(**kwargs)
    ...     return instances
    ...
    >>> plan, fulfilled_args = plan_for_func(fn, is_injectable=[A, B])
    >>> instances = build(plan)
    >>> kwargs = {arg: instances[arg_cls] for arg, arg_cls in fulfilled_args.items()}
    >>> fn(non_annotated='non_annotated', **kwargs)
    'Called with a, b, non_annotated'


    :param func: Function to be inspected.
    :param is_injectable: A predicate or a container that says if a type
        is injectable. The planer is responsible to deal
        with all types that are injectable when traversing
        the dependency graph. It fails with
        ``NonProvidableError`` if it is not possible to generate
        a plan for any of the injectable type found.
    :param externally_provided: A predicate or a dictionary that says if
        a class will be provided externally. The planner won't try to resolve
        its dependencies, so it acts as a way to stop dependency injection
        for these classes where we don't want it because they will be
        provided by other means.
    :param strict: If the argument ``strict`` is True then this function fails
        with ``NonProvidableError`` if not all the required arguments
        for the input function can be resolved. When ``strict`` is False, this
        function provides the plan only for those arguments that could
        be resolved.
    :return: A tuple where the first element is the plan and the second is
        a dictionary with the arguments that finally it was possible to
        generate a plan for.
    """
    assert not isinstance(func, type)
    is_injectable, externally_provided = _ensure_input_type_checks_as_func(
        is_injectable, externally_provided)
    plan = _plan(func,
                 is_injectable=is_injectable,
                 externally_provided=externally_provided,
                 strict=strict,
                 dependency_stack=None)
    fulfilled_arguments = plan.pop(_FunctionArguments)
    return plan, fulfilled_arguments


def plan_for_class(cls: Type, *,
                   is_injectable: TypeContainerOrCallable,
                   externally_provided: Optional[TypeContainerOrCallable] = None
                   ) -> Plan:
    """ Plan the sequence of instantiation tasks required to create an instance
    of the given cls.

    Equivalent to function ``plan_for_func`` but for a class.

    Note that is function raises ``NonProvidableError`` if is not
    possible to create a plan for building the given class.

    See function ``plan_for_func`` for a explanation of the rest of arguments.

    The following doctest example shows how this function can be used to create
    instances of the class ``C``:

    >>> class A:
    ...     pass
    ...
    >>> class B:
    ...     def __init__(self, a: A):
    ...         self.a = a
    ...
    >>> class C:
    ...     def __init__(self, a: A, b: B):
    ...         self.a = a
    ...         self.b = b
    ...
    >>> def build(plan):  # Build all the instances from a plan
    ...     instances = {}
    ...     for cls, args in plan.items():
    ...         kwargs = {arg: instances[arg_cls]
    ...                   for arg, arg_cls in args.items()}
    ...         instances[cls] = cls(**kwargs)
    ...     return instances
    ...
    >>> plan = plan_for_class(C, is_injectable={A, B, C})
    >>> instances = build(plan)
    >>> c = instances[C]  # Instance of C class with all dependencies resolved
    >>> assert type(c) is C
    >>> assert c.a is instances[A]
    >>> assert c.b is instances[B]
    >>> assert c.b.a is instances[A]
    """
    assert isinstance(cls, type)
    is_injectable, externally_provided = _ensure_input_type_checks_as_func(
        is_injectable, externally_provided)
    return _plan(cls,
                 is_injectable=is_injectable,
                 externally_provided=externally_provided,
                 strict=True,
                 dependency_stack=None)


def _plan(class_or_func: Union[Type, Callable], *,
          is_injectable: Callable[[Type], bool],
          externally_provided: Callable[[Type], bool],
          strict,
          dependency_stack=None) -> Plan:
    dependency_stack = dependency_stack or []
    plan_seq = OrderedDict()  # type: Plan
    type_for_arg = {}

    input_is_type = isinstance(class_or_func, type)

    if input_is_type:
        cls = cast(Type, class_or_func)
        if externally_provided(cls):
            plan_seq[cls] = {}
            return plan_seq

        if not is_injectable(cls):
            raise NonProvidableError(
                "Type {} cannot be provided".format(cls))


        if cls in dependency_stack:
            raise CyclicDependencyError(
                "Cyclic dependency found. Dependency graph: {}".format(
                    " -> ".join(map(str, dependency_stack + [cls]))))
        dependency_stack = dependency_stack + [cls]
        arguments = inspect(cls.__init__)
    else:
        arguments = inspect(class_or_func)

    for argname, types in arguments.items():
        sel_cls = _select_type(types, is_injectable, externally_provided)
        if sel_cls is not None:
            if sel_cls not in plan_seq:
                plan = _plan(sel_cls,
                             is_injectable=is_injectable,
                             externally_provided=externally_provided,
                             strict=True,
                             dependency_stack=dependency_stack)
                plan_seq.update(plan)
            type_for_arg[argname] = sel_cls
        else:
            if input_is_type or strict:
                if not types:
                    msg = "Parameter '{}' is lacking annotations in " \
                          "'{}.__init__()'. Not possible to build a plan".format(
                        argname, class_or_func)
                else:
                    msg = "Any of {} types are required ".format(types)
                    msg += " for parameter '{}' ".format(argname)
                    msg += " in '{}.__init__()' but none can be provided".format(
                        class_or_func)
                raise NonProvidableError(msg)


    plan_seq[cls if input_is_type else _FunctionArguments] = type_for_arg
    return plan_seq


def _select_type(types, is_injectable, externally_provided):
    """ Choose the first type that can be provided. None otherwise. """
    for candidate in types:
        if is_injectable(candidate) or externally_provided(candidate):
            return candidate


def _ensure_can_provide_func(cont_or_call: Optional[TypeContainerOrCallable]
                             ) -> Callable[[Type], bool]:
    if cont_or_call is None:
        return lambda x: False
    if isinstance(cont_or_call, Container):
        return cont_or_call.__contains__
    return cont_or_call


def _ensure_input_type_checks_as_func(can_provide, externally_provided
                                      ) -> Tuple[Callable[[Type], bool],
                                               Callable[[Type], bool]]:
    assert can_provide is not None
    can_provide = _ensure_can_provide_func(can_provide)
    externally_provided = _ensure_can_provide_func(externally_provided)
    return can_provide, externally_provided


class _FunctionArguments:
    """ Key marker to return the inspected function arguments into the
    ``Plan`` returned by the ``_plan`` function """
    pass
