from collections import OrderedDict, defaultdict
from collections.abc import Callable, Container, Mapping, MutableMapping
from dataclasses import dataclass
from inspect import Parameter, signature
from typing import Any, TypeAlias

from andi.errors import (
    CyclicDependencyErrCase,
    ErrCase,
    LackingAnnotationErrCase,
    NonInjectableOrExternalErrCase,
    NonProvidableError,
)
from andi.typeutils import (
    get_callable_func_obj,
    get_globalns,
    get_type_hints_with_extras,
    get_unannotated_params,
    get_union_args,
    is_union,
    strip_annotated,
)


def inspect(class_or_func: Callable[..., Any]) -> dict[str, list[Any]]:
    """
    For each argument of the ``class_or_func`` return a list of possible types.
    Non annotated arguments are also returned with an empty list of possible
    types.

    ``class_or_func`` can be

    * a function
    * a class - in this case ``cls.__init__`` annotations are returned
    * a callable object - in this case ``obj.__call__`` annotations
      are returned

    The elements of the returned lists are the objects produced by
    ``typing.get_type_hints(..., include_extras=True)``, with ``Union`` /
    ``Optional`` annotations flattened into their members. They are therefore
    not necessarily ``type`` objects: an ``Annotated[X, ...]`` annotation, for
    example, is kept as-is.
    """
    func = get_callable_func_obj(class_or_func)
    globalns = get_globalns(func)
    annotations = get_type_hints_with_extras(func, globalns)
    for name in get_unannotated_params(func, annotations):
        annotations[name] = None
    annotations.pop("return", None)
    annotations.pop("self", None)  # FIXME: pop first argument of methods
    annotations.pop("cls", None)
    res: dict[str, list[Any]] = {}
    for key, tp in annotations.items():
        if is_union(tp):
            res[key] = get_union_args(tp)
        elif tp is None:
            res[key] = []
        else:
            res[key] = [tp]
    return res


def _params_with_default_value(class_or_func: Callable[..., Any]) -> set[str]:
    """Return a set with the names of the parameters of *class_or_func* that
    have a default value."""
    result: set[str] = set()
    try:
        sig = signature(class_or_func)
    except ValueError:  # e.g. built-in types.
        return result
    for name, metadata in sig.parameters.items():
        if metadata.default is not Parameter.empty:
            result.add(name)
    return result


ContainerOrCallableType: TypeAlias = Container[Any] | Callable[[Any], bool]


class KwargsSpec(dict[str, Callable[..., Any]]):
    """
    kwargs specification. Dict with the name of the argument
    and the callable that is required to build an instance for such argument.
    """

    def kwargs(self, instances: Mapping[Callable[..., Any], Any]) -> dict[str, Any]:
        """
        Build the kwargs dict based on the spec using the prebuilt
        instances provided in the input dictionary.

        :param instances: A dict with the already prebuilt dependencies keyed
                          by its builder
        :return: a kwargs dict ready to be passed to a callable
        """
        return {name: instances[cls] for name, cls in self.items()}


@dataclass(frozen=True)
class CustomBuilder:
    result_class_or_fn: Callable[..., Any]
    factory: Callable[..., Any]


Step: TypeAlias = tuple[Callable[..., Any] | CustomBuilder, KwargsSpec]


class Plan(list[Step]):
    """
    The resultant plan of executing the ``plan`` function.
    It contains a sequence of steps that should be executed in order because
    they are dependant among them.

    The plan is itself a list of tuples of type
    ``tuple[Callable | CustomBuilder, KwargsSpec]``. Note that
    ``KwargsSpec`` is almost a ``dict[str, Callable]``
    so each step in the plan corresponds to
    (callable_or_custom_builder, (argument_name -> callable_to_build_the_argument)).

    The first element of a step is usually the class/function to invoke, but it
    can also be a :class:`CustomBuilder` when the step is built through a
    ``custom_builder_fn`` (see ``plan``). Consumers iterating over the plan must
    handle that case, e.g. with ``isinstance(fn_or_cls, CustomBuilder)``.

    ``plan.full_final_kwargs`` is ``True`` if ``final_kwargs`` function
    returns a ``kwargs`` dict containing absolutely all arguments required
    to invoke the class/function. In other words, returned dict is not a
    incomplete set of ``kwargs``.
    """

    def __init__(self, *args: Any, full_final_kwargs: bool = False, **kwargs: Any):
        self.full_final_kwargs = full_final_kwargs
        super().__init__(*args, **kwargs)

    @property
    def dependencies(self) -> list[Step]:
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

    def final_kwargs(
        self, instances: Mapping[Callable[..., Any], Any]
    ) -> dict[str, Any]:
        """
        Build the kwargs dict required to invoke the class/function
        for which the plan was done for.
        Equivalent to ``plan[-1][1].kwargs(instances)``

        :param instances: A dict with the already prebuilt dependencies keyed
                          by its builder
        :return: a kwargs dict ready to be passed to a callable
        """
        return self[-1][1].kwargs(instances)


OverrideFn: TypeAlias = Callable[[Any], Callable[..., Any] | None]
CustomBuilderFn: TypeAlias = Callable[[Any], Callable[..., Any] | None]


def plan(
    class_or_func: Callable[..., Any],
    *,
    is_injectable: ContainerOrCallableType,
    externally_provided: ContainerOrCallableType | None = None,
    full_final_kwargs: bool = False,
    overrides: OverrideFn | None = None,
    recursive_overrides: bool = False,
    custom_builder_fn: CustomBuilderFn = lambda _: None,
) -> Plan:
    """Plan the sequence of instantiation steps required to fulfill the
    the arguments of the given function or the arguments of its
    constructor if a class is given instead. In other words, this function
    makes dependency injection easy. Type annotations are used
    to determine which instance must be built to satisfy the dependency.

    The plan is a sequence of steps.
    Each step in the plan is a tuple with:

    * A callable with the class/function that must be built/invoked in this
      step, or a :class:`CustomBuilder` when ``custom_builder_fn`` provides a
      factory for that step.
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
                if isinstance(fn_or_cls, CustomBuilder):
                    instances[fn_or_cls.result_class_or_fn] = fn_or_cls.factory(**kwargs)
                else:
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
    ...         kwargs = kwargs_spec.kwargs(instances)
    ...         if isinstance(fn_or_cls, CustomBuilder):
    ...             instances[fn_or_cls.result_class_or_fn] = fn_or_cls.factory(**kwargs)
    ...         else:
    ...             instances[fn_or_cls] = fn_or_cls(**kwargs)
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
    :param overrides: A function that maps a class/function to a different
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
    :param custom_builder_fn: A function that takes a callable and returns a
        different callable if that needs to be called instead of the original one
        (e.g. when a class needs to be created using a factory instead of its
        constructor) and None otherwise.
    :return: A plan
    """
    is_injectable = _ensure_can_provide_func(is_injectable)
    externally_provided = _ensure_can_provide_func(externally_provided)
    overrides = overrides or _empty_overrides
    class_or_func, overrides = _may_override(
        class_or_func, overrides, recursive_overrides
    )

    plan, _ = _plan(
        class_or_func,
        is_injectable=is_injectable,
        externally_provided=externally_provided,
        full_final_kwargs=full_final_kwargs,
        dependency_stack=None,
        overrides=overrides,
        recursive_overrides=recursive_overrides,
        custom_builder_fn=custom_builder_fn,
    )
    return plan


def _plan(
    class_or_func: Callable[..., Any],
    *,
    is_injectable: Callable[[Any], bool],
    externally_provided: Callable[[Any], bool],
    full_final_kwargs: bool,
    dependency_stack: list[Callable[..., Any] | CustomBuilder] | None = None,
    overrides: OverrideFn,
    recursive_overrides: bool = False,
    custom_builder_fn: CustomBuilderFn = lambda _: None,
    custom_builder_result: Callable[..., Any] | None = None,
) -> tuple[Plan, list[ErrCase]]:
    dependency_stack = dependency_stack or []
    is_root_call = not dependency_stack  # For better code reading
    plan_od: MutableMapping[Callable[..., Any] | CustomBuilder, KwargsSpec] = (
        OrderedDict()
    )
    type_for_arg = KwargsSpec()

    if externally_provided(strip_annotated(class_or_func)):
        return Plan([(class_or_func, KwargsSpec())], full_final_kwargs=True), []

    plan_key: Callable[..., Any] | CustomBuilder
    if not custom_builder_result:
        plan_key = class_or_func
    else:
        plan_key = CustomBuilder(custom_builder_result, class_or_func)

    # At this point the class/function must be injectable or built by a custom builder for non root cases
    assert (
        is_root_call
        or custom_builder_result
        or is_injectable(strip_annotated(class_or_func))
    )

    if class_or_func in dependency_stack:
        return Plan(), [CyclicDependencyErrCase(class_or_func, dependency_stack)]

    dependency_stack = [*dependency_stack, plan_key]
    arguments = inspect(class_or_func)
    have_default = _params_with_default_value(class_or_func)

    args_errs: dict[str, list[ErrCase]] = defaultdict(list)
    non_injectable_errs: dict[str, list[ErrCase]] = defaultdict(list)
    for argname, types in arguments.items():
        sel_cls, arg_overrides = _select_type(
            types,
            is_injectable,
            externally_provided,
            overrides,
            recursive_overrides,
            custom_builder_fn,
        )
        if sel_cls is not None:
            errors: list[ErrCase] = []
            if sel_cls not in plan_od:
                run_plan = True
                custom_builder = custom_builder_fn(sel_cls)
                if custom_builder:
                    custom_builder_args = inspect(custom_builder)
                    for arg_types in custom_builder_args.values():
                        if class_or_func in arg_types:
                            # Break the cycle by ignoring the custom builder.
                            # This allows building an object externally and then using it to build
                            # another object of the same type, via a custom builder.
                            if not externally_provided(sel_cls):
                                non_injectable_errs[argname].append(
                                    NonInjectableOrExternalErrCase(
                                        argname, class_or_func, types
                                    )
                                )
                                run_plan = False
                            custom_builder = None
                            break
                if run_plan:
                    plan, errors = _plan(
                        custom_builder or sel_cls,
                        is_injectable=is_injectable,
                        externally_provided=externally_provided,
                        full_final_kwargs=True,
                        dependency_stack=dependency_stack,
                        overrides=arg_overrides,
                        recursive_overrides=recursive_overrides,
                        custom_builder_fn=custom_builder_fn,
                        custom_builder_result=sel_cls if custom_builder else None,
                    )
                    plan_od.update(plan)
            if errors:
                args_errs[argname].extend(errors)
            else:
                type_for_arg[argname] = sel_cls
        elif argname not in have_default:
            err_case: ErrCase
            if not types:
                err_case = LackingAnnotationErrCase(argname, class_or_func)
            else:
                err_case = NonInjectableOrExternalErrCase(argname, class_or_func, types)
            non_injectable_errs[argname].append(err_case)

    # Error managing
    if full_final_kwargs:
        args_errs.update(non_injectable_errs)
    if is_root_call and args_errs:
        raise NonProvidableError(class_or_func, args_errs)

    # Plan filling
    if not args_errs:
        plan_od[plan_key] = type_for_arg
    plan = Plan(plan_od.items(), full_final_kwargs=not non_injectable_errs)
    flatten_errors = [error for errors in args_errs.values() for error in errors]
    return plan, flatten_errors


def _select_type(
    types: list[Any],
    is_injectable: Callable[[Any], bool],
    externally_provided: Callable[[Any], bool],
    overrides: OverrideFn,
    recursive_overrides: bool,
    custom_builder_fn: CustomBuilderFn = lambda _: None,
) -> tuple[Callable[..., Any] | None, OverrideFn]:
    """
    Choose the first type that can be provided. None otherwise. Also return
    the overrides function to be used from now on.
    """
    for candidate in types:
        candidate, new_overrides = _may_override(  # noqa: PLW2901
            candidate, overrides, recursive_overrides
        )
        candidate_stripped = strip_annotated(candidate)
        if (
            is_injectable(candidate_stripped)
            or externally_provided(candidate_stripped)
            or custom_builder_fn(candidate_stripped) is not None
        ):
            return candidate, new_overrides
    return None, overrides


def _empty_overrides(class_or_func: Any) -> Callable[..., Any] | None:
    return None


def _may_override(
    class_or_func: Any, overrides: OverrideFn, recursive_overrides: bool
) -> tuple[Callable[..., Any], OverrideFn]:
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


def _ensure_can_provide_func(
    cont_or_call: ContainerOrCallableType | None,
) -> Callable[[Any], bool]:
    if cont_or_call is None:
        return lambda x: False
    if isinstance(cont_or_call, Container):
        return cont_or_call.__contains__
    return cont_or_call
