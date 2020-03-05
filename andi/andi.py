# -*- coding: utf-8 -*-
from collections import OrderedDict
from typing import (
    Dict, List, Optional, Type, Callable, Union, Container,
    get_type_hints, Tuple, cast, MutableMapping)

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


ContainerOrCallableType = Union[
    Container[Callable],
    Callable[[Callable], bool]
]


def to_provide(
        arguments_or_func: Union[
            Callable,
            Dict[str, List[Optional[Type]]]
        ],
        is_injectable: ContainerOrCallableType
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


PlanMapping = MutableMapping[Type, Dict[str, Type]]


class Plan(PlanMapping):
    """
    The plan resultant of executing the ``plan`` function.
    """

    def __init__(self):
        self._plan = OrderedDict()

    def __getitem__(self, item):
        return self._plan.__getitem__(item)

    def __setitem__(self, key, value):
        return self._plan.__setitem__(key, value)

    def __delitem__(self, key):
        return self._plan.__delitem__(key)

    def __iter__(self):
        return self._plan.__iter__()

    def __len__(self):
        return self._plan.__len__()

    def __str__(self):
        return self._plan.__str__()

    def __repr__(self):
        return self._plan.__repr__()

    @property
    def dependencies(self) -> PlanMapping:
        """
        The plan for build the dependencies of the last task of the plan.
        Useful when it is known that the last task of the plan could be
        incomplete, that is, not all dependencies for the last task could be
        resolved. In such a case is convenient to execute the plan
        for the dependencies and the have a custom execution for the
        last task of the plan.
        """
        return OrderedDict(list(self.items())[:-1])

    @property
    def final_arguments(self) -> Dict[str, Type]:
        """
         The argument names and its types for those arguments for
         which it was possible to fulfil the dependencies.
        """
        _, params = list(self.items())[-1]
        return params


def plan(class_or_func: Callable, *,
         is_injectable: ContainerOrCallableType,
         externally_provided: Optional[ContainerOrCallableType] = None,
         strict=False) -> Plan:
    """ Plan the sequence of instantiation tasks required to fulfill the
    the arguments of the given function or the arguments of its
    constructor if a class is given instead. In other words, this function
    makes dependency injection easy. Type annotations are used
    to determine with instance must be built to satisfy the dependency.

    The plan is a sequence encoded in a dict that preserves the order.
    Each task in the plan contains:

    * A key, with the class/function that must be built/invoked in this task
    * The value, which a dictionary with all the kwargs required for the
      key build/invocation process. This dictionary has the argument names as keys
      and classes/functions as values.

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
    dependencies for the class/function given as argument, but also all the
    dependencies of the dependencies. In other words, the plan function
    is able to plan the whole tree of dependencies.

    If the argument ``strict`` is True then this function will fail
    with ``NonProvidableError`` if not all the required arguments
    for the input class/function can be resolved. When ``strict`` is False, this
    function provides the plan only for those arguments that could be resolved.

    In other words, the last task in the plan could be incomplete when
    ``strict=False`` (for example, when some arguments are not annotated
    because they will be provided by other means).
    In such a cases the above proposed ``build`` function won't work.

    The plan methods ``dependencies`` and ``final_arguments`` comes to the
    rescue in such cases, and the build process would be slightly different::

        plan = andi.plan(func, ...)
        instances = build(plan.dependencies)
        kwargs = {arg: instances[arg_cls]
                  for arg, arg_cls in plan.final_arguments.items()}
        func(
            other_arg='value, # argument that is out of the scope of dependency injection
            **kwargs,
        )

    Any type found in the dependency tree that is injectable can as well
    has its own dependencies. If the planner fails to fulfill the dependencies 
    of any injectable found in the tree, ``NonProvidableError`` will be raised, 
    regardless of a value of ``strict`` argument (even if strict=False).

    This function recursively checks for dependencies. If a cyclic dependency
    is found, ``CyclicDependencyError`` is raised.

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
    >>> def _get_kwargs(instances, kwarg_types):
    ...     return {name: instances[cls] for name, cls in kwarg_types.items()}
    ...
    >>> def build(plan):  # Build all the instances from a plan
    ...     instances = {}
    ...     for cls, args in plan.items():
    ...         instances[cls] = cls(**_get_kwargs(instances, args))
    ...     return instances
    ...
    >>> plan_tasks = plan(fn, is_injectable=[A, B])
    >>> instances = build(plan_tasks.dependencies)
    >>> # Finally invoking the function with all the dependencies resolved
    >>> fn(non_annotated='non_annotated',
    ...    **_get_kwargs(instances, plan_tasks.final_arguments))
    'Called with a, b, non_annotated'

    The returned plan when ``strict=True`` is given can be directly built. See
    the following example:
    >>> class C:
    ...     def __init__(self, a: A, b: B):
    ...         self.a = a
    ...         self.b = b
    ...
    >>> plan_tasks = plan(C, is_injectable=[A, B, C], strict=True)
    >>> instances = build(plan_tasks)
    >>> c = instances[C]  # Instance of C class with all dependencies resolved
    >>> assert type(c) is C
    >>> assert c.a is instances[A]
    >>> assert c.b is instances[B]
    >>> assert c.b.a is instances[A] # Instance of A is reused (singleton)

    :param func: Function to be inspected.
    :param is_injectable: A predicate or a container that says if a type
        is injectable. The planer is responsible to deal
        with all types that are injectable when traversing
        the dependency graph. It fails with
        ``NonProvidableError`` if it is not possible to generate
        a plan for any of the injectable type found during the inspection.
    :param externally_provided: A predicate or a dictionary that says if
        the value for the class/function will be provided externally.
        The planner won't try to resolve
        its dependencies, so it acts as a way to stop dependency injection
        for these classes/functions where we don't want it because they will be
        provided by other means.
    :param strict: If the argument ``strict`` is True then this function fails
        with ``NonProvidableError`` if not all the required arguments
        for the input class/function can be resolved. When ``strict`` is False,
        this function provides the plan only for those arguments that could
        be resolved, so the last task of the plan could be incomplete.
    :return: A plan
    """
    is_injectable, externally_provided = _ensure_input_type_checks_as_func(
        is_injectable, externally_provided)
    plan = _plan(class_or_func,
                 is_injectable=is_injectable,
                 externally_provided=externally_provided,
                 strict=strict,
                 dependency_stack=None)
    return plan


def _plan(class_or_func: Callable, *,
          is_injectable: Callable[[Callable], bool],
          externally_provided: Callable[[Callable], bool],
          strict,
          dependency_stack=None) -> Plan:
    dependency_stack = dependency_stack or []
    plan_seq = Plan()
    type_for_arg = {}

    if externally_provided(class_or_func):
        plan_seq[class_or_func] = {}
        return plan_seq

    if not is_injectable(class_or_func) and dependency_stack:
        raise NonProvidableError(
            "Type {} cannot be provided".format(class_or_func))

    if class_or_func in dependency_stack:
        raise CyclicDependencyError(
            "Cyclic dependency found. Dependency graph: {}".format(
                " -> ".join(map(str, dependency_stack + [class_or_func]))))

    dependency_stack = dependency_stack + [class_or_func]

    if isinstance(class_or_func, type):
        cls = cast(Type, class_or_func)
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
            if strict:
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

    plan_seq[class_or_func] = type_for_arg
    return plan_seq


def _select_type(types, is_injectable, externally_provided):
    """ Choose the first type that can be provided. None otherwise. """
    for candidate in types:
        if is_injectable(candidate) or externally_provided(candidate):
            return candidate


def _ensure_can_provide_func(cont_or_call: Optional[ContainerOrCallableType]
                             ) -> Callable[[Callable], bool]:
    if cont_or_call is None:
        return lambda x: False
    if isinstance(cont_or_call, Container):
        return cont_or_call.__contains__
    return cont_or_call


def _ensure_input_type_checks_as_func(can_provide, externally_provided
                                      ) -> Tuple[Callable[[Callable], bool],
                                               Callable[[Callable], bool]]:
    assert can_provide is not None
    can_provide = _ensure_can_provide_func(can_provide)
    externally_provided = _ensure_can_provide_func(externally_provided)
    return can_provide, externally_provided

