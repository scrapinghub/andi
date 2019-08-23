# -*- coding: utf-8 -*-
from typing import Union, List


def is_union(tp) -> bool:
    """ Return True if a passed type is a typing.Union.

    >>> is_union(Union[int, str])
    True
    >>> is_union(str)
    False
    >>> is_union(Union)
    False
    >>> is_union(List[str])
    False
    """
    return hasattr(tp, "__origin__") and tp.__origin__ is Union


def get_union_args(tp) -> List:
    """ Return a list of typing.Union args.
    NoneType objects are converted to None for simplicity.
    """
    return _none_type_to_none(tp.__args__)


def _none_type_to_none(lst):
    return [(el if el is not None.__class__ else None) for el in lst]


def issubclass_safe(cls, bases) -> bool:
    """ like issubclass, but return False if cls is not a class, instead of
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
