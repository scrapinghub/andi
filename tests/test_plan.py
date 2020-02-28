from typing import Union, Optional

import pytest

import andi
from tests.utils import build
from andi import NonProvidableError


class A:

    def __init__(self, e: 'E'):
        pass


class B:
    pass


class C:

    def __init__(self, a: A, b: B):
        pass


class D:

    def __init__(self, a: A, c: C):
        pass


class E:

    def __init__(self, b: B, c: C, d: D):
        pass


ALL = [A, B, C, D, E]
SOME = [A, B, C]


def test_plan_and_build():
    plan = andi.plan_for_class(E, is_injectable=lambda x: True,
                               externally_provided=[A])

    assert set(list(plan.keys())[:2]) == {A, B}
    assert list(plan.values())[:2] == [{}, {}]
    assert list(plan.items())[2:] == [
        (C, {'a': A, 'b': B}),
        (D, {'a': A, 'c': C}),
        (E, {'b': B, 'c': C, 'd': D})
    ]
    instances = build(plan, {A: ""})
    assert type(instances[E]) == E


def test_cyclic_dependency():
    andi.plan_for_class(E, is_injectable=lambda x: True,
                        externally_provided=[A])  # No error if externally provided
    with pytest.raises(andi.CyclicDependencyError):
        andi.plan_for_class(E, is_injectable=lambda x: True,
                            externally_provided=[])


@pytest.mark.parametrize("cls,is_injectable,externally_provided", [
    (E, ALL, SOME),
    (C, SOME, ALL),
    (E, ALL, ALL)
])
def test_plan_container_or_func(cls, is_injectable, externally_provided):
    plan_func = andi.plan_for_class(cls, is_injectable=is_injectable,
                                    externally_provided=externally_provided)
    plan_container = andi.plan_for_class(cls, is_injectable=is_injectable,
                                         externally_provided=externally_provided)
    assert plan_func == plan_container


def test_cannot_be_provided():
    class WithB:

        def __init__(self, b: B):
            pass

    plan = list(andi.plan_for_class(WithB, is_injectable=[WithB, B],
                                    externally_provided=[B]).items())
    assert plan == [(B, {}), (WithB, {"b": B})]
    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithB, is_injectable=[WithB])
    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithB, is_injectable=[])

    class WithOptionals:

        def __init__(self, a_or_b: Union[A, B]):
            pass

    plan = list(andi.plan_for_class(WithOptionals,
                                    is_injectable=[WithOptionals, A, B],
                                    externally_provided=[A]).items())
    assert plan == [(A, {}), (WithOptionals, {'a_or_b': A})]

    plan = list(andi.plan_for_class(WithOptionals,
                                    is_injectable=[WithOptionals, B],
                                    externally_provided=[A]).items())
    assert plan == [(A, {}), (WithOptionals, {'a_or_b': A})]

    plan = list(andi.plan_for_class(WithOptionals,
                                    is_injectable=[WithOptionals, B]).items())
    assert plan == [(B, {}), (WithOptionals, {'a_or_b': B})]

    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithOptionals,
                            is_injectable=[WithOptionals]).items()


def test_externally_provided():
    plan, fulfilled_args = andi.plan_for_func(E.__init__, is_injectable=ALL,
                                              externally_provided=ALL)
    assert plan == {B: {}, C: {}, D: {}}
    assert fulfilled_args == {'b': B, 'c': C, 'd': D}

    plan, fulfilled_args = andi.plan_for_func(E.__init__, is_injectable=[],
                                              externally_provided=ALL)
    assert plan == {B: {}, C: {}, D: {}}
    assert fulfilled_args == {'b': B, 'c': C, 'd': D}

    plan = andi.plan_for_class(E, is_injectable=ALL, externally_provided=ALL)
    assert plan == {E: {}}

    plan = andi.plan_for_class(E, is_injectable=ALL,
                               externally_provided=[A, B, C, D])
    assert plan.keys() == {B, C, D, E}
    assert list(plan.keys())[-1] == E
    assert plan[E] == {'b': B, 'c': C, 'd': D}

    plan = andi.plan_for_class(E, is_injectable=ALL,
                               externally_provided=[A, B, D])
    seq = list(plan.keys())
    assert seq.index(A) < seq.index(C)
    assert seq.index(B) < seq.index(C)
    assert seq.index(D) < seq.index(E)
    assert seq.index(C) < seq.index(E)
    for cls in (A, B, D):
        assert plan[cls] == {}
    assert plan[C] == {'a': A, 'b': B}
    assert plan[E] == {'b': B, 'c': C, 'd': D}


def test_plan_for_func():
    def fn(other: str, e: E, c: C):
        assert other == 'yeah!'
        assert type(e) == E
        assert type(c) == C

    plan, fulfilled_args = andi.plan_for_func(fn, is_injectable=ALL,
                                              externally_provided=[A])
    assert fulfilled_args == {'e': E, 'c': C}
    instances = build(plan, {A: ""})
    kwargs = dict(other="yeah!",
                  **{arg: instances[tp] for arg, tp in fulfilled_args.items()})
    fn(**kwargs)

    with pytest.raises(NonProvidableError):
        andi.plan_for_func(fn, is_injectable=ALL,
                           externally_provided=[A], strict=True)


def test_plan_with_optionals():
    def fn(a: Optional[str]):
        assert a is None

    assert andi.plan_for_func(fn, is_injectable=[type(None), str],
                              externally_provided=[str]) == ({str: {}}, {'a': str})
    plan, fulfilled_args = andi.plan_for_func(fn, is_injectable=[type(None)])
    assert plan == {type(None): {}}
    assert fulfilled_args == {'a': type(None)}
    instances = build(plan)
    assert instances[type(None)] is None
    fn(**{arg: instances[tp] for arg, tp in fulfilled_args.items()})


def test_plan_class_non_annotated():
    class WithNonAnnArgs:

        def __init__(self, a: A, b: B, non_ann, non_ann_def=0, *,
                     non_ann_kw, non_ann_kw_def=1):
            pass

    plan, fulfilled_args = andi.plan_for_func(
        WithNonAnnArgs.__init__,
        is_injectable=ALL + [WithNonAnnArgs],
        externally_provided=[A]
    )
    assert plan == {A: {}, B: {}}
    assert fulfilled_args == {'a': A, 'b': B}

    with pytest.raises(andi.NonProvidableError):
        andi.plan_for_class(WithNonAnnArgs, is_injectable=ALL + [WithNonAnnArgs],
                            externally_provided=[A])


@pytest.mark.parametrize("strict", [(True), (False)])
def test_plan_no_args(strict):
    def fn():
        return True

    plan, fulfilled_args = andi.plan_for_func(fn, is_injectable=[],
                                              strict=strict)
    assert plan == {}
    assert fulfilled_args == {}
    instances = build(plan)
    assert fn(**{arg: instances[tp] for arg, tp in fulfilled_args.items()})
