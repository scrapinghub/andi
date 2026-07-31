import sys
from collections.abc import Callable
from functools import partial, wraps
from typing import Annotated, Any, Optional, TypeVar, Union

import pytest

import andi
from tests.types_pep563 import fn_unresolvable_annotation


class Foo:
    pass


class Bar:
    pass


class Baz:
    pass


def test_andi() -> None:
    def func1(x: Foo) -> None:
        pass

    def func2() -> None:
        pass

    def func3(x: Bar, y: Foo) -> None:
        pass

    assert andi.inspect(Foo.__init__) == {}
    assert andi.inspect(func1) == {"x": [Foo]}
    assert andi.inspect(func2) == {}
    assert andi.inspect(func3) == {"x": [Bar], "y": [Foo]}


def test_union() -> None:
    def func(x: Union[Foo, Bar]) -> None:  # noqa: UP007
        pass

    assert andi.inspect(func) == {"x": [Foo, Bar]}


def test_union_pipe() -> None:
    def func(x: Foo | Bar) -> None:
        pass

    assert andi.inspect(func) == {"x": [Foo, Bar]}


def test_optional() -> None:
    def func(x: Optional[Foo]) -> None:  # noqa: UP045
        pass

    assert andi.inspect(func) == {"x": [Foo, type(None)]}


def test_optional_pipe() -> None:
    def func(x: Foo | None) -> None:
        pass

    assert andi.inspect(func) == {"x": [Foo, type(None)]}


def test_optional_union() -> None:
    def func(x: Optional[Union[Foo, Baz]]) -> None:  # noqa: UP007, UP045
        pass

    assert andi.inspect(func) == {"x": [Foo, Baz, type(None)]}


def test_optional_union_pipe() -> None:
    def func(x: Foo | Baz | None) -> None:
        pass

    assert andi.inspect(func) == {"x": [Foo, Baz, type(None)]}


def test_not_annotated() -> None:
    # ``x`` is left unannotated on purpose
    def func(x) -> None:  # type: ignore[no-untyped-def]
        pass

    assert andi.inspect(func) == {"x": []}


def test_string_types() -> None:
    def func(x: "Bar") -> None:
        pass

    assert andi.inspect(func) == {"x": [Bar]}


def test_string_types_with_fn() -> None:
    """String type references not supported for __init__ in classes declared
    within functions"""

    class Fuu:
        def __init__(self, bur: "Bur"):
            pass

    class Bur:
        pass

    with pytest.raises(NameError):
        andi.inspect(Fuu.__init__)


def test_unresolvable_annotation_names_the_callable() -> None:
    with pytest.raises(NameError, match="fn_unresolvable_annotation"):
        andi.inspect(fn_unresolvable_annotation)


@pytest.mark.skipif(
    sys.version_info < (3, 14),
    reason="Annotations are evaluated when the signature is defined",
)
def test_unresolvable_lazy_annotation_names_the_callable() -> None:
    def func(a: Unresolvable) -> None:  # type: ignore[name-defined] # noqa: F821
        pass

    with pytest.raises(NameError, match="func"):
        andi.inspect(func)


def test_init_methods() -> None:
    class MyClass:
        def __init__(self, x: Foo):
            self.x = x

    assert andi.inspect(MyClass.__init__) == {"x": [Foo]}
    assert andi.inspect(MyClass) == {"x": [Foo]}


def test_classmethod() -> None:
    T = TypeVar("T")

    class MyClass:
        @classmethod
        def from_foo(cls: type[T], foo: Foo) -> T:  # noqa: PYI019
            return cls()

    assert andi.inspect(MyClass.from_foo) == {"foo": [Foo]}


def test_decorated() -> None:
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return fn(*args, **kwargs)

        return wrapper

    @decorator
    def func(x: "Bar") -> None:
        pass

    assert andi.inspect(func) == {"x": [Bar]}


@pytest.mark.xfail(reason="functools.partial support is not implemented")
def test_partial() -> None:
    def func(x: Foo, y: Bar) -> None:
        pass

    func_nofoo = partial(func, x=Foo())
    assert andi.inspect(func_nofoo) == {"y": [Bar]}


def test_callable_object() -> None:
    class MyClass:
        def __call__(self, x: Bar) -> None:
            pass

    obj = MyClass()
    assert andi.inspect(obj) == {"x": [Bar]}


def test_annotations() -> None:
    def f(x: Annotated[int, 42]) -> None:
        pass

    assert andi.inspect(f) == {"x": [Annotated[int, 42]]}
