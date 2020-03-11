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
        elif tp is None:
            res[key] = []
        else:
            res[key] = [tp]
    return res


ContainerOrCallableType = Union[
    Container[Callable],
    Callable[[Callable], bool]
]


PlanStepList = List[Tuple[Callable, Dict[str, Callable]]]


class Plan(PlanStepList):
    """
    The resultant plan of executing the ``plan`` function.
    It contains a sequence of steps that should be executed in order because
    they are dependant among them.

    The plan is itself a list of tuples of type
    ``Tuple[Callable, Dict[str, Callable]]``
    corresponding to
    (callable_to_invoke, (param_name -> callable_to_build_the_param)).
    """

    @property
    def dependencies(self) -> PlanStepList:
        """
        The plan required to build the dependencies for the
        ``plan`` input function/class only.
        Useful when it is known that not all dependencies for input
        function/class could be resolved. In such a case, it is convenient to
        execute the plan for the dependencies and then
        have a custom execution step for the
        input function/class where those non-resolvable dependencies are
        provided by other means.

        ``plan.dependencies`` is the ``plan`` without the last item ``plan[:-1]``
        """
        return self[:-1]

    @property
    def final_arguments(self) -> Dict[str, Callable]:
        """
        The input function/class argument names and its builders for
        those arguments for which it was possible to resolve the dependencies.

        Equivalent to ``self[-1][1]``
        """
        _, params = self[-1]
        return params


def plan(class_or_func: Callable, *,
         is_injectable: ContainerOrCallableType,
         externally_provided: Optional[ContainerOrCallableType] = None,
         strict=False) -> Plan:
    """ Plan the sequence of instantiation steps required to fulfill the
    the arguments of the given function or the arguments of its
    constructor if a class is given instead. In other words, this function
    makes dependency injection easy. Type annotations are used
    to determine with instance must be built to satisfy the dependency.

    The plan is a sequence steps.
    Each step in the plan is a tuple with:

    * A callable with the
      class/function that must be built/invoked in this step
    * A dictionary with all the kwargs required for the
      key build/invocation process. This dictionary has the argument names as keys
      and classes/functions required to build them as values.

    The best way to understand a plan is to see how a typical building
    function would use it to build the instances::

        def build(plan):  # Build all the instances from a plan
            instances = {}
            for fn_or_cls, args in plan:
                kwargs = {arg: instances[arg_cls]
                          for arg, arg_cls in args.items()}
                instances[fn_or_cls] = fn_or_cls(**kwargs)
            return instances

    Note that the generated instances dictionary would contain not only the
    dependencies for the class/function given as argument, but also all the
    dependencies of the dependencies. In other words, the plan function
    is able to plan the whole tree of dependencies.

    If the argument ``strict`` is True then this function will fail
    with ``NonProvidableError`` if not all the required arguments
    for the input class/function can be resolved. When ``strict`` is False, this
    function provides the plan only for those arguments that could be resolved.

    In other words, the step for the input function/class
    (which always corresponds with the last step) could be incomplete when
    ``strict=False`` (for example, when some arguments are not annotated
    because they will be provided by other means).
    In such a cases the above proposed ``build`` function won't work.

    The plan properties ``dependencies`` and ``final_arguments`` come to the
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
    of any injectable found in the tree, ``NonProvidableError`` is raised, 
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
    ...     for fn_or_cls, args in plan:
    ...         instances[fn_or_cls] = fn_or_cls(**_get_kwargs(instances, args))
    ...     return instances
    ...
    >>> plan_steps = plan(fn, is_injectable={A, B})
    >>> instances = build(plan_steps.dependencies)
    >>> # Finally invoking the function with all the dependencies resolved
    >>> fn(non_annotated='non_annotated',
    ...    **_get_kwargs(instances, plan_steps.final_arguments))
    'Called with a, b, non_annotated'

    The returned plan when ``strict=True`` is given can be directly built. See
    the following example:
    >>> class C:
    ...     def __init__(self, a: A, b: B):
    ...         self.a = a
    ...         self.b = b
    ...
    >>> plan_steps = plan(C, is_injectable={A, B, C}, strict=True)
    >>> instances = build(plan_steps)
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
    is_injectable = _ensure_can_provide_func(is_injectable)
    externally_provided = _ensure_can_provide_func(externally_provided)

    plan_odict = _plan(class_or_func,
                 is_injectable=is_injectable,
                 externally_provided=externally_provided,
                 strict=strict,
                 dependency_stack=None)
    return Plan(plan_odict.items())


_PlanDict = MutableMapping[Callable, Dict[str, Callable]]

def _plan(class_or_func: Callable, *,
          is_injectable: Callable[[Callable], bool],
          externally_provided: Callable[[Callable], bool],
          strict,
          dependency_stack=None) -> _PlanDict:
    dependency_stack = dependency_stack or []
    plan_seq = OrderedDict()  # type: _PlanDict
    type_for_arg = {}

    if externally_provided(class_or_func):
        plan_seq[class_or_func] = {}
        return plan_seq

    if dependency_stack and not is_injectable(class_or_func):
        raise NonProvidableError(
            "Type {} cannot be provided".format(class_or_func))

    if class_or_func in dependency_stack:
        raise CyclicDependencyError(
            "Cyclic dependency found. Dependency graph: {}".format(
                " -> ".join(map(str, dependency_stack + [class_or_func]))))

    dependency_stack = dependency_stack + [class_or_func]

    is_class = isinstance(class_or_func, type)
    if is_class:
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
                init_str = ".__init__()" if is_class else ""
                if not types:
                    msg = "Parameter '{}' is lacking annotations in " \
                          "'{}{}'. Not possible to build a plan".format(
                        argname, class_or_func, init_str)
                else:
                    msg = "Any of {} types are required ".format(types)
                    msg += " for parameter '{}' ".format(argname)
                    msg += " in '{}{}' but none can be provided".format(
                        class_or_func, init_str)
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
