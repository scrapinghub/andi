import functools
import inspect
import sys
import types
from collections.abc import Callable, Container
from typing import Annotated, Union, get_args, get_origin, get_type_hints


def is_union(tp) -> bool:
    """Return True if a passed type is a typing.Union.

    >>> is_union(Union[int, str])
    True
    >>> is_union(str)
    False
    >>> is_union(Union)
    False
    >>> is_union(list[str])
    False
    """
    return hasattr(tp, "__origin__") and tp.__origin__ is Union


def get_type_hints_with_extras(obj, *args, **kwargs):
    """
    Like get_type_hints, but sets include_extras=True
    """
    kwargs["include_extras"] = True
    return get_type_hints(obj, *args, **kwargs)


def get_union_args(tp) -> list:
    """Return a list of typing.Union args."""
    return list(tp.__args__)


def issubclass_safe(cls, bases) -> bool:
    """like issubclass, but return False if cls is not a class, instead of
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


def get_unannotated_params(func, annotations: Container) -> list[str]:
    """Return a list of ``func`` argument names which are not type annotated.

    ``annotations`` should be a result of get_type_hints call for ``func``.

    >>> from typing import get_type_hints
    >>> def foo(x, y: str, *, z, w: int, **kwargs): pass
    >>> annotations = get_type_hints(foo)
    >>> get_unannotated_params(foo, annotations)
    ['x', 'z']
    """
    ARGS_KWARGS = {
        inspect.Parameter.VAR_POSITIONAL,  # *args argument
        inspect.Parameter.VAR_KEYWORD,  # **kwargs argument
    }
    res = []
    for name, param in inspect.signature(func).parameters.items():
        if name in annotations or param.kind in ARGS_KWARGS:
            continue
        res.append(name)
    return res


def get_globalns(func: Callable) -> dict:
    """Return the global namespace that will be used for the resolution
    of postponed type annotations.

    Based on ``typing.get_type_hints`` code, with a workaround for ``attrs``
    issue.
    """
    ns = dict(_get_globalns_for_attrs(func))
    ns.update(_get_globalns_as_get_type_hints(func))
    return ns


def _get_globalns_as_get_type_hints(func: Callable) -> dict:
    """Global namespace resolution extracted from ``get_type_hints`` method.
    Python 3.7 (https://github.com/python/cpython/blob/3.7/Lib/typing.py#L981-L988)
    Note that this is only supporting functions as input."""
    nsobj = func
    # Find globalns for the unwrapped object.
    while hasattr(nsobj, "__wrapped__"):
        nsobj = nsobj.__wrapped__
    return getattr(nsobj, "__globals__", {})


def _get_globalns_for_attrs(func: Callable) -> dict:
    """Adds partial support for postponed type annotations in attrs classes.
    Also required to support attrs classes when
    ``from __future__ import annotations`` is used (default for python 4.0).
    See https://github.com/python-attrs/attrs/issues/593"""
    if getattr(func, "__module__", None) in sys.modules:
        return dict(sys.modules[func.__module__].__dict__)
    # Theoretically this can happen if someone writes
    # a custom string to func.__module__.  In which case
    # such attrs might not be fully introspectable
    # (w.r.t. typing.get_type_hints) but will still function
    # correctly.
    return {}


# from typing module (near get_type_hints), but without ModuleType
_FUNCTION_TYPES = (
    types.FunctionType,
    types.BuiltinFunctionType,
    types.MethodType,
    types.WrapperDescriptorType,
    types.MethodWrapperType,
    types.MethodDescriptorType,
)


def get_callable_func_obj(class_or_func: Callable) -> Callable:
    """
    Return a function/method which will be invoked
    when func(...) is called. The resulting object should be
    supported by ``get_type_hints``.
    """
    if not callable(class_or_func):
        raise TypeError(f"{class_or_func!r} is not callable")
    if isinstance(class_or_func, type):
        # see https://github.com/python/typing/discussions/1331
        return class_or_func.__init__  # type: ignore[misc]
    # we need to check some exact types, because some function-like
    # object also have __call__ method, while it is better
    # not to use it, as get_type_hints support these objects as-is
    if isinstance(class_or_func, _FUNCTION_TYPES):
        return class_or_func
    if isinstance(class_or_func, functools.partial):
        raise NotImplementedError(
            f"functools.partial support is not implemented; {class_or_func!r} is passed"
        )
    if hasattr(class_or_func, "__call__"):  # noqa: B004
        return class_or_func.__call__
    # not sure how to trigger it
    raise TypeError(f"Unexpected callable object {class_or_func!r}")


def is_typing_annotated(o: Callable) -> bool:
    """Return True if the input is typing.Annotated"""
    return get_origin(o) == Annotated


def strip_annotated(o: Callable) -> Callable:
    """Return the underlying type for Annotated, the input itself otherwise."""
    if is_typing_annotated(o):
        return get_args(o)[0]
    return o
