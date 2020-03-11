from typing import Union, Optional

import pytest

import andi
from andi import NonProvidableError
from tests.utils import build
from collections import OrderedDict as OD

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
    plan = andi.plan(E, is_injectable=lambda x: True,
                     externally_provided={A})

    assert dict(plan[:2]).keys() == {A, B}
    assert list(dict(plan[:2]).values()) == [{}, {}]
    assert plan[2:] == [
        (C, {'a': A, 'b': B}),
        (D, {'a': A, 'c': C}),
        (E, {'b': B, 'c': C, 'd': D})
    ]
    instances = build(plan, {A: ""})
    assert type(instances[E]) == E


def test_cyclic_dependency():
    andi.plan(E, is_injectable=lambda x: True,
              externally_provided={A})  # No error if externally provided
    with pytest.raises(andi.CyclicDependencyError):
        andi.plan(E, is_injectable=lambda x: True, externally_provided=[])


@pytest.mark.parametrize("cls,is_injectable,externally_provided", [
    (E, ALL, SOME),
    (C, SOME, ALL),
    (E, ALL, ALL)
])
def test_plan_similar_for_class_or_func(cls, is_injectable, externally_provided):
    is_injectable = is_injectable + [cl.__init__ for cl in is_injectable]
    externally_provided = externally_provided + [cl.__init__
                                                 for cl in externally_provided]
    external_deps = {cl: "external" for cl in externally_provided}

    plan_cls = andi.plan(cls, is_injectable=is_injectable,
                         externally_provided=externally_provided)
    plan_func = andi.plan(cls.__init__, is_injectable=is_injectable,
                          externally_provided=externally_provided)

    plan_func[-1] = (cls, plan_func[-1][1])  # To make plans compatible
    assert plan_cls == plan_func

    instances = build(plan_cls, external_deps)
    assert type(instances[cls]) == cls or instances[cls] == "external"
    instances = build(plan_func, external_deps)
    assert type(instances[cls]) == cls or instances[cls] == "external"


def test_cannot_be_provided():
    class WithC:

        def __init__(self, c: C):
            pass

    plan = andi.plan(WithC, is_injectable={B, C}, externally_provided={A})
    assert dict(plan) == {A: {}, B: {}, C: {'a': A, 'b': B}, WithC: {'c': C}}

    # partial plan also allowed (C is not required to be injectable):
    andi.plan(WithC, is_injectable={B}, externally_provided={A})

    # But should fail on full_final_arguments regimen
    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithC, is_injectable={B}, externally_provided={A},
                  full_final_arguments=True)

    # C is injectable, but A and B are not injectable. So an exception is raised:
    # every single injectable dependency found must be satisfiable.
    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithC, is_injectable=[C])


def test_plan_with_optionals():
    def fn(a: Optional[str]):
        assert a is None
        return "invoked!"

    plan = andi.plan(fn, is_injectable={type(None), str},
                     externally_provided={str})
    assert plan ==  [(str, {}), (fn, {'a': str})]

    plan = andi.plan(fn, is_injectable={type(None)})
    assert plan.dependencies == [(type(None), {})]
    assert plan.final_arguments == {'a': type(None)}

    instances = build(plan)
    assert instances[type(None)] is None
    assert instances[fn] == "invoked!"

    with pytest.raises(andi.NonProvidableError):
        andi.plan(fn, is_injectable={}, full_final_arguments=True)


def test_plan_with_union():
    class WithUnion:

        def __init__(self, a_or_b: Union[A, B]):
            pass

    plan = andi.plan(WithUnion,
                     is_injectable={WithUnion, A, B},
                     externally_provided={A})
    assert plan == [(A, {}), (WithUnion, {'a_or_b': A})]

    plan = andi.plan(WithUnion,
                     is_injectable={WithUnion, B},
                     externally_provided={A})
    assert plan == [(A, {}), (WithUnion, {'a_or_b': A})]

    plan = andi.plan(WithUnion, is_injectable={WithUnion, B})
    assert plan == [(B, {}), (WithUnion, {'a_or_b': B})]

    plan = andi.plan(WithUnion, is_injectable={WithUnion},
                     externally_provided={B})
    assert plan == [(B, {}), (WithUnion, {'a_or_b': B})]

    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithUnion, is_injectable={WithUnion}, full_final_arguments=True)

    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithUnion, is_injectable={}, full_final_arguments=True)


def test_plan_with_optionals_and_union():
    def fn(str_or_b_or_None: Optional[Union[str, B]]):
        return str_or_b_or_None

    plan = andi.plan(fn, is_injectable={str, B, type(None)})
    assert type(build(plan)[fn]) == str

    plan = andi.plan(fn, is_injectable={B, type(None)})
    assert type(build(plan)[fn]) == B

    plan = andi.plan(fn, is_injectable={B, type(None)},
                     externally_provided={str})
    assert type(build(plan)[fn]) == str

    plan = andi.plan(fn, is_injectable={type(None)})
    assert build(plan)[fn] is None

    plan = andi.plan(fn, is_injectable={type(None)},
                     externally_provided={str})
    assert type(build(plan)[fn]) == str

    plan = andi.plan(fn, is_injectable={type(None)},
                     externally_provided={str, B})
    assert type(build(plan)[fn]) == str

    plan = andi.plan(fn, is_injectable={type(None)},
                     externally_provided={B})
    assert type(build(plan)[fn]) == B

    with pytest.raises(NonProvidableError):
        andi.plan(fn, is_injectable={}, full_final_arguments=True)


def test_externally_provided():
    plan = andi.plan(E.__init__, is_injectable=ALL,
                     externally_provided=ALL)
    assert dict(plan.dependencies) == {B: {}, C: {}, D: {}}
    assert plan.final_arguments == {'b': B, 'c': C, 'd': D}

    plan = andi.plan(E.__init__, is_injectable=[],
                     externally_provided=ALL)
    assert dict(plan.dependencies) == {B: {}, C: {}, D: {}}
    assert plan.final_arguments == {'b': B, 'c': C, 'd': D}

    plan = andi.plan(E, is_injectable=ALL, externally_provided=ALL)
    assert plan == [(E, {})]
    assert plan.final_arguments == {}
    assert plan.dependencies == []

    plan = andi.plan(E, is_injectable=ALL,
                     externally_provided={A, B, C, D})
    assert dict(plan).keys() == {B, C, D, E}
    assert plan[-1][0] == E
    assert plan.final_arguments == {'b': B, 'c': C, 'd': D}
    assert plan.final_arguments == plan[-1][1]

    plan = andi.plan(E, is_injectable=ALL,
                     externally_provided={A, B, D})
    plan_od = OD(plan)
    seq = list(plan_od.keys())
    assert seq.index(A) < seq.index(C)
    assert seq.index(B) < seq.index(C)
    assert seq.index(D) < seq.index(E)
    assert seq.index(C) < seq.index(E)
    for cls in (A, B, D):
        assert plan_od[cls] == {}
    assert plan_od[C] == {'a': A, 'b': B}
    assert plan_od[E] == {'b': B, 'c': C, 'd': D}


def test_plan_for_func():
    def fn(other: str, e: E, c: C):
        assert other == 'yeah!'
        assert type(e) == E
        assert type(c) == C

    plan = andi.plan(fn, is_injectable=ALL,
                     externally_provided={A})
    assert plan.final_arguments == {'e': E, 'c': C}
    instances = build(plan.dependencies, {A: ""})
    kwargs = dict(other="yeah!",
                  **{arg: instances[tp]
                     for arg, tp in plan.final_arguments.items()})
    fn(**kwargs)

    with pytest.raises(TypeError):
        build(plan, {A: ""})

    with pytest.raises(andi.NonProvidableError):
        andi.plan(fn, is_injectable=ALL,
                  externally_provided=[A], full_final_arguments=True)


def test_plan_non_annotated_args():
    class WithNonAnnArgs:

        def __init__(self, a: A, b: B, non_ann, non_ann_def=0, *,
                     non_ann_kw, non_ann_kw_def=1):
            pass

    plan = andi.plan(
        WithNonAnnArgs.__init__,
        is_injectable=ALL,
        externally_provided={A}
    )

    assert dict(plan.dependencies) == {A: {}, B: {}}
    assert plan.final_arguments == {'a': A, 'b': B}

    plan_class = andi.plan(WithNonAnnArgs,
                           is_injectable=ALL,
                           externally_provided=[A])
    assert plan_class.dependencies == plan.dependencies
    assert plan_class.final_arguments == plan.final_arguments

    with pytest.raises(TypeError):
        build(plan)

    instances = build(plan.dependencies, instances_stock={A: ""})
    o = WithNonAnnArgs(non_ann=None, non_ann_kw=None,
                       **{arg: instances[tp] for arg, tp
                          in plan.final_arguments.items()})
    assert isinstance(o, WithNonAnnArgs)

    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithNonAnnArgs, is_injectable=ALL, externally_provided=[A],
                  full_final_arguments=True)


@pytest.mark.parametrize("full_final_arguments", [[True], [False]])
def test_plan_no_args(full_final_arguments):
    def fn():
        return True

    plan = andi.plan(fn, is_injectable=[],
                     full_final_arguments=full_final_arguments)
    assert plan == [(fn, {})]
    instances = build(plan)
    assert instances[fn]
    assert fn(
        **{arg: instances[tp] for arg, tp in plan.final_arguments.items()})


@pytest.mark.parametrize("full_final_arguments", [[True], [False]])
def test_plan_use_fn_as_annotations(full_final_arguments):
    def fn_ann(b: B):
        setattr(b, "modified", True)
        return b

    def fn(b: fn_ann):
        return b

    plan = andi.plan(fn, is_injectable=[fn_ann, B], full_final_arguments=full_final_arguments)
    instances = build(plan)
    assert instances[fn].modified
