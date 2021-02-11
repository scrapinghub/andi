# -*- coding: utf-8 -*-
from collections import OrderedDict, defaultdict
from typing import (
    Dict, List, Optional, Type, Callable, Union, Container,
    get_type_hints, Tuple, MutableMapping, Any, Mapping)

from andi.typeutils import (
    get_union_args,
    is_union,
    get_globalns,
    get_unannotated_params,
    get_callable_func_obj,
)
from andi.errors import (
    NonProvidableError,
    CyclicDependencyErrCase,
    LackingAnnotationErrCase,
    NonInjectableOrExternalErrCase
)


def inspect(class_or_func: Callable) -> Dict[str, List[Optional[Type]]]:
    """
    For each argument of the ``class_or_func`` return a list of possible types.
    Non annotated arguments are also returned with an empty list of possible
    types.

    ``class_or_func`` can be

    * a function
    * a class - in this case ``cls.__init__`` annotations are returned
    * a callable object - in this case ``obj.__call__`` annotations
      are returned
    """
    func = get_callable_func_obj(class_or_func)
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


class KwargsSpec(Dict[str, Callable]):
    """
    kwargs specification. Dict with the name of the argument
    and the callable that is required to build an instance for such argument.
    """

    def kwargs(self, instances: Mapping[Callable, Any]) -> Dict[str, Any]:
        """
        Build the kwargs dict based on the spec using the prebuilt
        instances provided in the input dictionary.

        :param instances: A dict with the already prebuilt dependencies keyed
                          by its builder
        :return: a kwargs dict ready to be passed to a callable
        """
        return {name: instances[cls] for name, cls in self.items()}


Step = Tuple[Callable, KwargsSpec]


class Plan(List[Step]):
    """
    The resultant plan of executing the ``plan`` function.
    It contains a sequence of steps that should be executed in order because
    they are dependant among them.

    The plan is itself a list of tuples of type
    ``Tuple[Callable, KwargsSpec]``. Note that
    ``KwargsSpec`` is almost a ``Dict[str, Callable]``
    so each step in the plan corresponds to
    (callable_to_invoke, (argument_name -> callable_to_build_the_argument)).

    ``plan.full_final_kwargs`` is ``True`` if ``final_kwargs`` function
    returns a ``kwargs`` dict containing absolutely all arguments required
    to invoke the class/function. In other words, returned dict is not a
    incomplete set of ``kwargs``.
    """

    def __init__(self, *args, full_final_kwargs: bool = False, **kwargs):
        self.full_final_kwargs = full_final_kwargs
        super().__init__(*args, **kwargs)

    @property
    def dependencies(self) -> List[Step]:
        """
        The plan required to build the dependencies only for the
        ``plan`` input function/class.
        Useful when it is known that not all dependencies for input
        function/class could be resolved. In such a case, it is convenient to
        execute the plan for the dependencies and then
        have a custom execution step for the
        input function/class where those non-resolvable dependencies are
        provided by other means.

        ``plan.dependencies`` is the ``plan`` without the last item ``plan[:-1]``
        """
        return self[:-1]

    def final_kwargs(self, instances: Mapping[Callable, Any]) -> Dict[str, Any]:
        """
        Build the kwargs dict required to invoke the class/function
        for which the plan was done for.
        Equivalent to ``plan[-1][1].kwargs(instances)``

        :param instances: A dict with the already prebuilt dependencies keyed
                          by its builder
        :return: a kwargs dict ready to be passed to a callable
        """
        return self[-1][1].kwargs(instances)


OverrideFn = Callable[[Callable], Optional[Callable]]


def plan(class_or_func: Callable, *,
         is_injectable: ContainerOrCallableType,
         externally_provided: Optional[ContainerOrCallableType] = None,
         full_final_kwargs=False,
         overrides: Optional[OverrideFn] = None,
         recursive_overrides: bool = False) -> Plan:
    """ Plan the sequence of instantiation steps required to fulfill the
    the arguments of the given function or the arguments of its
    constructor if a class is given instead. In other words, this function
    makes dependency injection easy. Type annotations are used
    to determine which instance must be built to satisfy the dependency.

    The plan is a sequence of steps.
    Each step in the plan is a tuple with:

    * A callable with the
      class/function that must be built/invoked in this step
    * A ``KwargsSpec`` with all the kwargs required for the
      build/invocation process. This is a dictionary-like object with
      the argument names as keys
      and classes/functions required to build them as values.

    The best way to understand a plan is to see how a typical building
    function would use it to build the instances::

        def build(plan):  # Build all the instances from a plan
            instances = {}
            for fn_or_cls, kwargs_spec in plan:
                kwargs = {arg: instances[arg_builder]
                          for arg, arg_builder in kwargs_spec.items()}
                # or alternatively: kwargs = kwargs_spec.kwargs(instances)
                instances[fn_or_cls] = fn_or_cls(**kwargs)
            return instances

    Note that the generated instances dictionary would contain not only the
    dependencies for the class/function given as argument, but also all the
    dependencies of the dependencies. In other words, the plan function
    is able to plan the whole tree of dependencies.

    If the argument ``full_final_kwargs`` is True then this function will fail
    with ``NonProvidableError`` if not all the required arguments
    for the input class/function can be resolved. When
    ``full_final_kwargs`` is False, this
    function provides the plan only for those arguments that could be resolved.

    In other words, the step for the input function/class
    (which always corresponds with the last step) could be incomplete when
    ``full_final_kwargs=False`` (for example, when some
    arguments are not annotated
    because they will be provided by other means).
    In such a cases the above proposed ``build`` function won't work.

    The plan properties ``dependencies`` and ``final_kwargs`` come to the
    rescue in such cases, and the build process would be slightly different::

        plan = andi.plan(func, ...)
        instances = build(plan.dependencies)
        func(
            other_arg='value, # argument that is provided manually
            **plan.final_kwargs(instances),
        )

    Any type found in the dependency tree that is injectable can as well
    has its own dependencies. If the planner fails to fulfill the dependencies 
    of any injectable found in the tree, ``NonProvidableError`` is raised, 
    regardless of a value of ``full_final_kwargs``
    argument (even if full_final_kwargs=False).

    This function recursively checks for dependencies. If a cyclic dependency
    is found, ``NonProvidableError`` is raised.

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
    ...     for fn_or_cls, kwargs_spec in plan:
    ...         instances[fn_or_cls] = fn_or_cls(**kwargs_spec.kwargs(instances))
    ...     return instances
    ...
    >>> plan_steps = plan(fn, is_injectable={A, B})
    >>> instances = build(plan_steps.dependencies)
    >>> # Finally invoking the function with all the dependencies resolved
    >>> fn(non_annotated='non_annotated',
    ...    **plan_steps.final_kwargs(instances))
    'Called with a, b, non_annotated'

    The returned plan can be directly built when ``full_final_kwargs=True``
    is given. See the following example:
    >>> class C:
    ...     def __init__(self, a: A, b: B):
    ...         self.a = a
    ...         self.b = b
    ...
    >>> plan_steps = plan(C, is_injectable={A, B, C}, full_final_kwargs=True)
    >>> instances = build(plan_steps)
    >>> c = instances[C]  # Instance of C class with all dependencies resolved
    >>> assert type(c) is C
    >>> assert c.a is instances[A]
    >>> assert c.b is instances[B]
    >>> assert c.b.a is instances[A] # Instance of A is reused (singleton)
    >>> assert plan_steps.full_final_kwargs


    :param class_or_func: Class/Function to plan for building/invocation.
    :param is_injectable: A predicate or a container that says if a type
        is injectable. The planer is responsible to deal
        with all types that are injectable when traversing
        the dependency graph. It fails with
        ``NonProvidableError`` if it is not possible to generate
        a plan for any of the injectable type found during the inspection.
    :param externally_provided: A predicate or a dictionary that says if
        the value for the class/function will be provided externally.
        The planner won't try to resolve
        its dependencies, so it acts as a way to stop dependency planning
        for these classes/functions where we don't want it because they will be
        provided by other means.
    :param full_final_kwargs: If the argument ``full_final_kwargs``
        is True then this function fails
        with ``NonProvidableError`` if not all the required arguments
        for the input class/function can be resolved.
        When ``full_final_kwargs`` is False,
        this function provides the plan only for those arguments that could
        be resolved, so the last task of the plan could be incomplete.
        In other words, the kwargs dict returned by the method
        ``Plan.final_kwargs`` could not contain all required
        arguments to build/invoke the input class/function.
    :param overrides: A funtion that maps a class/function to a different
        class/function. The function must return None if no special mapping should
        be applied for a particular class/function. The suggested remapping serves
        to override a particular dependency in the dependency tree, and
        update the plan acordingly. For example, you might want to replace class
        ``PenneWithTomate`` by ``SpaghettiBolognese`` whenever it is find in the
        dependendy tree, but updating the plan so that ``SpaghettiBolognese``
        gets its dependencies ``Meat`` and ``Spaghetti`` resolved properly.
    :param recursive_overrides: If True, ``overrides`` are applied recursively
        to the children dependencies of an overriden class/function.
        If False, overrides are not applied to the children of an
        overriden node in the dependency tree. Consider the following example.
        The class ``PriceInEur`` is wanted to be overriden by the class
        ``PriceInDollar``, but the later requires using ``PriceInEur`` and then
        apply an
        exchange rate over the price. That is, ``PriceInDollar`` depends on the
        class we want to override. If ``recursive_overrides`` is True, then
        an error is raised because a cyclid dependency would have been found:
        the dependency of ``PriceInDollar``, which is ``PriceInEur``, will
        be also overriden by ``PriceInDollar`` override, leading to a cyclic dependency.
        That had't be the case if ``recursive_overrides`` would have been False.
        In such a case, the override won't have been applied to the dependency of
        ``PriceInDollar``, so the plan would have succeed.
    :return: A plan
    """
    is_injectable = _ensure_can_provide_func(is_injectable)
    externally_provided = _ensure_can_provide_func(externally_provided)
    overrides = overrides or _empty_overrides
    class_or_func, overrides = _may_override(class_or_func, overrides, recursive_overrides)

    plan, _ = _plan(class_or_func,
                    is_injectable=is_injectable,
                    externally_provided=externally_provided,
                    full_final_kwargs=full_final_kwargs,
                    dependency_stack=None,
                    overrides=overrides,
                    recursive_overrides=recursive_overrides)
    return plan


def _plan(class_or_func: Callable, *,
          is_injectable: Callable[[Callable], bool],
          externally_provided: Callable[[Callable], bool],
          full_final_kwargs,
          dependency_stack=None,
          overrides: Callable[[Callable], Optional[Callable]],
          recursive_overrides: bool = False
          ) -> Tuple[Plan, List[Tuple]]:
    dependency_stack = dependency_stack or []
    is_root_call = not dependency_stack  # For better code reading
    plan_od = OrderedDict()  # type: MutableMapping[Callable, KwargsSpec]
    type_for_arg = KwargsSpec()

    if externally_provided(class_or_func):
        return Plan([(class_or_func, KwargsSpec())], full_final_kwargs=True), []

    # At this point the class/function must be injectable for non root cases
    assert is_root_call or is_injectable(class_or_func)

    if class_or_func in dependency_stack:
        return Plan(), [CyclicDependencyErrCase(class_or_func, dependency_stack)]

    dependency_stack = dependency_stack + [class_or_func]
    arguments = inspect(class_or_func)

    args_errs = defaultdict(list)  # type: Dict[str, List[Tuple]]
    non_injectable_errs = defaultdict(list)  # type: Dict[str, List[Tuple]]
    for argname, types in arguments.items():
        sel_cls, arg_overrides = _select_type(
            types, is_injectable, externally_provided, overrides, recursive_overrides)
        if sel_cls is not None:
            errors = []  # type: List[Tuple]
            if sel_cls not in plan_od:
                plan, errors = _plan(sel_cls,
                                     is_injectable=is_injectable,
                                     externally_provided=externally_provided,
                                     full_final_kwargs=True,
                                     dependency_stack=dependency_stack,
                                     overrides=arg_overrides,
                                     recursive_overrides=recursive_overrides)
                plan_od.update(plan)
            if errors:
                args_errs[argname].extend(errors)
            else:
                type_for_arg[argname] = sel_cls
        else:
            if not types:
                err_case = LackingAnnotationErrCase(argname, class_or_func)  # type: Tuple
            else:
                err_case = NonInjectableOrExternalErrCase(argname, class_or_func,
                                                          types)
            non_injectable_errs[argname].append(err_case)

    # Error managing
    if full_final_kwargs:
        args_errs.update(non_injectable_errs)
    if is_root_call and args_errs:
        raise NonProvidableError(class_or_func, args_errs)

    # Plan filling
    if not args_errs:
        plan_od[class_or_func] = type_for_arg
    plan = Plan(plan_od.items(), full_final_kwargs=not non_injectable_errs)
    flatten_errors = [error
                      for errors in args_errs.values()
                      for error in errors]
    return plan, flatten_errors


def _select_type(types,
                 is_injectable,
                 externally_provided,
                 overrides: Callable,
                 recursive_overrides: bool
                 ) -> Tuple[Optional[Callable], OverrideFn]:
    """
    Choose the first type that can be provided. None otherwise. Also return
    the overrides function to be used from now on.
    """
    for candidate in types:
        candidate, new_overrides = _may_override(
            candidate, overrides, recursive_overrides)
        if is_injectable(candidate) or externally_provided(candidate):
            return candidate, new_overrides
    return None, overrides


def _empty_overrides(class_or_func: Callable) -> Optional[Callable]:
    return None


def _may_override(class_or_func, overrides: OverrideFn, recursive_overrides: bool
                  ) -> Tuple[Callable, OverrideFn]:
    """
    May override ``class_or_func`` if ``overrides`` function suggest it.
    In such a case, ``overrides`` function is replaced with ``_empty_overrides``
    to stop overriding in children if recursive_overrides is disabled.
    """
    override = overrides(class_or_func)
    under_override = bool(override and override != class_or_func)
    class_or_func = override or class_or_func
    stop_overriding = not recursive_overrides and under_override
    overrides_for_children = _empty_overrides if stop_overriding else overrides
    return class_or_func, overrides_for_children


def _ensure_can_provide_func(cont_or_call: Optional[ContainerOrCallableType]
                             ) -> Callable[[Callable], bool]:
    if cont_or_call is None:
        return lambda x: False
    if isinstance(cont_or_call, Container):
        return cont_or_call.__contains__
    return cont_or_call
