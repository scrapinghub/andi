# -*- coding: utf-8 -*-
from functools import wraps, partial
from typing import Union, Optional, TypeVar, Type

import pytest

import andi


class Foo:
    pass


class Bar:
    pass


class Baz:
    pass


def test_andi():
    def func1(x: Foo):
        pass

    def func2():
        pass

    def func3(x: Bar, y: Foo):
        pass

    assert andi.inspect(Foo.__init__) == {}
    assert andi.inspect(func1) == {'x': [Foo]}
    assert andi.inspect(func2) == {}
    assert andi.inspect(func3) == {'x': [Bar], 'y': [Foo]}


def test_union():
    def func(x: Union[Foo, Bar]):
        pass

    assert andi.inspect(func) == {'x': [Foo, Bar]}


def test_optional():
    def func(x: Optional[Foo]):
        pass

    assert andi.inspect(func) == {'x': [Foo, type(None)]}


def test_optional_union():
    def func(x: Optional[Union[Foo, Baz]]):
        pass

    assert andi.inspect(func) == {'x': [Foo, Baz, type(None)]}


def test_not_annotated():
    def func(x):
        pass

    assert andi.inspect(func) == {'x': []}


def test_string_types():
    def func(x: 'Bar'):
        pass
    assert andi.inspect(func) == {'x': [Bar]}


def test_string_types_with_fn():
    """ String type references not supported for __init__ in classes declared
    within functions """

    class Fuu:
        def __init__(self, bur :'Bur'):
            pass

    class Bur:
        pass

    with pytest.raises(NameError):
        andi.inspect(Fuu.__init__)


def test_init_methods():
    class MyClass:
        def __init__(self, x: Foo):
            self.x = x

    assert andi.inspect(MyClass.__init__) == {'x': [Foo]}
    assert andi.inspect(MyClass) == {'x': [Foo]}


def test_classmethod():
    T = TypeVar('T')

    class MyClass:
        @classmethod
        def from_foo(cls: Type[T], foo: Foo) -> T:
            return cls()

    assert andi.inspect(MyClass.from_foo) == {'foo': [Foo]}


def test_decorated():
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            return fn(*args, **kwargs)
        return wrapper

    @decorator
    def func(x: 'Bar'):
        pass

    assert andi.inspect(func) == {'x': [Bar]}


@pytest.mark.xfail(reason="functools.partial support is not implemented")
def test_partial():
    def func(x: Foo, y: Bar):
        pass

    func_nofoo = partial(func, x=Foo())
    assert andi.inspect(func_nofoo) == {'y': [Bar]}


def test_callable_object():
    class MyClass:
        def __call__(self, x: Bar):
            pass

    obj = MyClass()
    assert andi.inspect(obj) == {'x': [Bar]}
