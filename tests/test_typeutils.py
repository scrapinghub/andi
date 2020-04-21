# -*- coding: utf-8 -*-
from typing import Union, Optional

import pytest

from andi.typeutils import get_union_args, get_callable_func_obj


def test_get_union_args():
    assert get_union_args(Union[str, int]) == [str, int]


def test_get_union_args_optional():
    assert get_union_args(Optional[Union[str, int]]) == [str, int, None.__class__]


def test_get_callable_func_obj_functions():
    def foo():
        pass

    assert get_callable_func_obj(foo) is foo


def test_get_callable_func_obj_class():

    class Foo:
        x = 5

        def __init__(self):
            pass

        def meth(self):
            pass

        @staticmethod
        def staticmeth(cls):
            pass

    foo = Foo()

    # happy path
    assert get_callable_func_obj(Foo) is Foo.__init__
    assert get_callable_func_obj(Foo.meth) is Foo.meth
    assert get_callable_func_obj(Foo.staticmeth) is Foo.staticmeth
    assert get_callable_func_obj(foo.meth) == foo.meth
    assert get_callable_func_obj(foo.staticmeth) is foo.staticmeth

    with pytest.raises(TypeError):
        get_callable_func_obj(Foo.x)  # type: ignore

    with pytest.raises(TypeError):
        get_callable_func_obj(foo)


def test_get_callable_func_classmethods():
    class Foo:
        @classmethod
        def clsmeth(cls):
            pass

    foo = Foo()

    assert get_callable_func_obj(Foo.clsmeth) == Foo.clsmeth
    assert get_callable_func_obj(foo.clsmeth) == foo.clsmeth


def test_get_callable_func_obj_call():
    class Foo:
        def __init__(self):
            pass

        def __call__(self):
            pass

        def meth(self):
            pass

    foo = Foo()

    assert get_callable_func_obj(Foo) is Foo.__init__
    assert get_callable_func_obj(foo.meth) == foo.meth
    assert get_callable_func_obj(foo) == foo.__call__
