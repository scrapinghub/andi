from typing import Annotated, Any, Optional, Union, get_type_hints

import pytest

from andi.typeutils import (
    get_callable_func_obj,
    get_type_hints_with_extras,
    get_union_args,
)


def test_get_union_args() -> None:
    assert get_union_args(Union[str, int]) == [str, int]  # noqa: UP007


def test_get_union_args_pipe() -> None:
    assert get_union_args(str | int) == [str, int]


def test_get_union_args_optional() -> None:
    assert get_union_args(Optional[Union[str, int]]) == [str, int, None.__class__]  # noqa: UP007,UP045


def test_get_union_args_optional_pipe() -> None:
    assert get_union_args(str | int | None) == [str, int, None.__class__]


def test_get_callable_func_obj_functions() -> None:
    def foo() -> None:
        pass

    assert get_callable_func_obj(foo) is foo


def test_get_callable_func_obj_class() -> None:
    class Foo:
        x = 5

        def __init__(self) -> None:
            pass

        def meth(self) -> None:
            pass

        @staticmethod
        def staticmeth(cls_: Any) -> None:
            pass

    foo = Foo()

    # happy path
    assert get_callable_func_obj(Foo) is Foo.__init__
    assert get_callable_func_obj(Foo.meth) is Foo.meth
    assert get_callable_func_obj(Foo.staticmeth) is Foo.staticmeth
    assert get_callable_func_obj(foo.meth) == foo.meth
    assert get_callable_func_obj(foo.staticmeth) is foo.staticmeth

    with pytest.raises(TypeError):
        get_callable_func_obj(Foo.x)  # type: ignore[arg-type]

    with pytest.raises(TypeError):
        get_callable_func_obj(foo)  # type: ignore[arg-type]


def test_get_callable_func_classmethods() -> None:
    class Foo:
        @classmethod
        def clsmeth(cls) -> None:
            pass

    foo = Foo()

    assert get_callable_func_obj(Foo.clsmeth) == Foo.clsmeth
    assert get_callable_func_obj(foo.clsmeth) == foo.clsmeth


def test_get_callable_func_obj_call() -> None:
    class Foo:
        def __init__(self) -> None:
            pass

        def __call__(self) -> None:
            pass

        def meth(self) -> None:
            pass

    foo = Foo()

    assert get_callable_func_obj(Foo) is Foo.__init__
    assert get_callable_func_obj(foo.meth) == foo.meth
    assert get_callable_func_obj(foo) == foo.__call__


def test_get_hint_extras() -> None:
    def f(x: Annotated[int, 42]) -> None:
        pass

    hints = get_type_hints(f)
    assert hints["x"] is int

    hints_annotated = get_type_hints_with_extras(f)
    assert hints_annotated["x"] == Annotated[int, 42]
