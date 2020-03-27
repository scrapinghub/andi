from functools import partial
from typing import Union, Optional

import pytest

import andi
from andi import NonProvidableError
from andi.andi import _class_or_func_str
from tests.utils import build
from collections import OrderedDict


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

    def __init__(self, d: D, c: C, b: B):
        pass


ALL = [A, B, C, D, E]
SOME = [A, B, C]


def _final_kwargs_spec(plan):
    return plan[-1][1]


@pytest.fixture
def captured_errors(monkeypatch):
    """
    Return a list that will capture the last errors raised by ``andi.plan``
    """
    def identity(tag):
        def iden_fn(*args):
            return (tag,) + args

        return iden_fn

    errors = []
    def capture_errors(class_or_func, arg_errors):
        errors.clear()
        # Sorting for determinism
        errors.extend(sorted(arg_errors.items(), key=lambda t: t[0]))
        for _, errs in errors:
            errs.sort(key=str)

    monkeypatch.setattr(andi.andi, "_cyclic_dependency_error", identity('cyclic'))
    monkeypatch.setattr(andi.andi, "_no_injectable_or_external_error", identity('no_inj'))
    monkeypatch.setattr(andi.andi, "_argument_lacking_annotation_error", identity('lack'))
    monkeypatch.setattr(andi.andi, "_exception_msg", capture_errors)

    return errors


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
    assert plan.full_final_kwargs
    instances = build(plan, {A: ""})
    assert type(instances[E]) == E


def test_cyclic_dependency(captured_errors):
    plan = andi.plan(E, is_injectable=lambda x: True,
              externally_provided={A})  # No error if externally provided
    with pytest.raises(andi.NonProvidableError):
        andi.plan(E, is_injectable=lambda x: True, externally_provided=[])
    expected_errors = [
        ('c', [('cyclic', E, [E, C, A])]),
        ('d', [
            ('cyclic', E, [E, D, A]),
            ('cyclic', E, [E, D, C, A]),
        ])
    ]

    with pytest.raises(andi.NonProvidableError):
        andi.plan(E, is_injectable=lambda x: True, externally_provided=[],
                  full_final_kwargs=True)
    assert captured_errors == expected_errors


@pytest.mark.parametrize("cls,is_injectable,externally_provided", [
    (E, ALL, SOME),
    (C, SOME, ALL),
    (E, ALL, ALL),
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
    assert plan_cls.full_final_kwargs
    assert plan_cls.full_final_kwargs == plan_func.full_final_kwargs


    instances = build(plan_cls, external_deps)
    assert type(instances[cls]) == cls or instances[cls] == "external"
    instances = build(plan_func, external_deps)
    assert type(instances[cls]) == cls or instances[cls] == "external"


def test_cannot_be_provided(captured_errors):
    class WithC:

        def __init__(self, c: C):
            pass

    plan = andi.plan(WithC, is_injectable={B, C}, externally_provided={A})
    assert dict(plan) == {A: {}, B: {}, C: {'a': A, 'b': B}, WithC: {'c': C}}
    assert plan.full_final_kwargs

    # partial plan also allowed (C is not required to be injectable):
    plan = andi.plan(WithC, is_injectable={B}, externally_provided={A})
    assert not plan.full_final_kwargs

    # But should fail on full_final_kwargs regimen
    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithC, is_injectable={B}, externally_provided={A},
                  full_final_kwargs=True)
    assert captured_errors == [('c', [('no_inj', 'c', WithC, [C])],)]

    # C is injectable, but A and B are not injectable. So an exception is raised:
    # every single injectable dependency found must be satisfiable.
    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithC, is_injectable=[C], full_final_kwargs=True)
    assert captured_errors == [
        ('c', [
            ('no_inj', 'a', C, [A]),
            ('no_inj', 'b', C, [B]),
        ]),
    ]


def test_plan_with_optionals(captured_errors):
    def fn(a: Optional[str]):
        assert a is None
        return "invoked!"

    plan = andi.plan(fn, is_injectable={type(None), str},
                     externally_provided={str})
    assert plan ==  [(str, {}), (fn, {'a': str})]
    assert plan.full_final_kwargs

    plan = andi.plan(fn, is_injectable={type(None)})
    assert plan.dependencies == [(type(None), {})]
    assert _final_kwargs_spec(plan) == {'a': type(None)}
    assert plan.full_final_kwargs

    instances = build(plan)
    assert instances[type(None)] is None
    assert instances[fn] == "invoked!"

    with pytest.raises(andi.NonProvidableError):
        andi.plan(fn, is_injectable={}, full_final_kwargs=True)
    assert captured_errors == [('a', [('no_inj', 'a', fn, [str, type(None)])])]


def test_plan_with_union(captured_errors):
    class WithUnion:

        def __init__(self, a_or_b: Union[A, B]):
            pass

    plan = andi.plan(WithUnion,
                     is_injectable={WithUnion, A, B},
                     externally_provided={A})
    assert plan == [(A, {}), (WithUnion, {'a_or_b': A})]
    assert plan.full_final_kwargs

    plan = andi.plan(WithUnion,
                     is_injectable={WithUnion, B},
                     externally_provided={A})
    assert plan == [(A, {}), (WithUnion, {'a_or_b': A})]
    assert plan.full_final_kwargs

    plan = andi.plan(WithUnion, is_injectable={WithUnion, B})
    assert plan == [(B, {}), (WithUnion, {'a_or_b': B})]
    assert plan.full_final_kwargs

    plan = andi.plan(WithUnion, is_injectable={WithUnion},
                     externally_provided={B})
    assert plan == [(B, {}), (WithUnion, {'a_or_b': B})]
    assert plan.full_final_kwargs

    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithUnion, is_injectable={WithUnion},
                  full_final_kwargs=True)
    assert captured_errors == [
        ('a_or_b', [('no_inj', 'a_or_b', WithUnion, [A, B])])
    ]

    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithUnion, is_injectable={}, full_final_kwargs=True)
    assert captured_errors == [
        ('a_or_b', [('no_inj', 'a_or_b', WithUnion, [A, B])])
    ]


def test_plan_with_optionals_and_union(captured_errors):
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

    plan = andi.plan(fn, is_injectable={})
    assert plan == [(fn, {})]
    assert not plan.full_final_kwargs

    with pytest.raises(NonProvidableError):
        andi.plan(fn, is_injectable={}, full_final_kwargs=True)
    assert captured_errors == [
        ('str_or_b_or_None', [
            ('no_inj', 'str_or_b_or_None', fn, [str, B, type(None)])
        ])
    ]



def test_externally_provided():
    plan = andi.plan(E.__init__, is_injectable=ALL,
                     externally_provided=ALL)
    assert dict(plan.dependencies) == {B: {}, C: {}, D: {}}
    assert _final_kwargs_spec(plan) == {'b': B, 'c': C, 'd': D}
    assert plan.full_final_kwargs

    plan = andi.plan(E.__init__, is_injectable=[],
                     externally_provided=ALL)
    assert dict(plan.dependencies) == {B: {}, C: {}, D: {}}
    assert _final_kwargs_spec(plan) == {'b': B, 'c': C, 'd': D}
    assert plan.full_final_kwargs

    plan = andi.plan(E, is_injectable=ALL, externally_provided=ALL)
    assert plan == [(E, {})]
    assert _final_kwargs_spec(plan) == {}
    assert plan.dependencies == []
    assert plan.full_final_kwargs

    plan = andi.plan(E, is_injectable=ALL,
                     externally_provided={A, B, C, D})
    assert dict(plan).keys() == {B, C, D, E}
    assert plan[-1][0] == E
    assert _final_kwargs_spec(plan) == {'b': B, 'c': C, 'd': D}
    assert _final_kwargs_spec(plan) == plan[-1][1]
    assert plan.full_final_kwargs

    plan = andi.plan(E, is_injectable=ALL,
                     externally_provided={A, B, D})
    plan_od = OrderedDict(plan)
    seq = list(plan_od.keys())
    assert seq.index(A) < seq.index(C)
    assert seq.index(B) < seq.index(C)
    assert seq.index(D) < seq.index(E)
    assert seq.index(C) < seq.index(E)
    for cls in (A, B, D):
        assert plan_od[cls] == {}
    assert plan_od[C] == {'a': A, 'b': B}
    assert plan_od[E] == {'b': B, 'c': C, 'd': D}
    assert plan.full_final_kwargs


def test_plan_for_func(captured_errors):
    def fn(other: str, e: E, c: C):
        assert other == 'yeah!'
        assert type(e) == E
        assert type(c) == C

    plan = andi.plan(fn, is_injectable=ALL,
                     externally_provided={A})
    assert _final_kwargs_spec(plan) == {'e': E, 'c': C}
    assert not plan.full_final_kwargs
    instances = build(plan.dependencies, {A: ""})
    fn(other="yeah!", **plan.final_kwargs(instances))

    with pytest.raises(TypeError):
        build(plan, {A: ""})

    with pytest.raises(andi.NonProvidableError):
        andi.plan(fn, is_injectable=ALL, externally_provided=[A],
                  full_final_kwargs=True)
    assert captured_errors == [('other', [('no_inj', 'other', fn, [str])])]



def test_plan_non_annotated_args(captured_errors):
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
    assert _final_kwargs_spec(plan) == {'a': A, 'b': B}
    assert not plan.full_final_kwargs

    plan_class = andi.plan(WithNonAnnArgs,
                           is_injectable=ALL,
                           externally_provided=[A])
    assert plan_class.dependencies == plan.dependencies
    assert _final_kwargs_spec(plan_class) == _final_kwargs_spec(plan)
    assert not plan.full_final_kwargs

    with pytest.raises(TypeError):
        build(plan)

    instances = build(plan.dependencies, instances_stock={A: ""})
    o = WithNonAnnArgs(non_ann=None, non_ann_kw=None,
                       **plan.final_kwargs(instances))
    assert isinstance(o, WithNonAnnArgs)

    with pytest.raises(andi.NonProvidableError):
        andi.plan(WithNonAnnArgs, is_injectable=ALL,
                  externally_provided=[A], full_final_kwargs=True)
    assert captured_errors == [
        ('non_ann', [('lack', 'non_ann', WithNonAnnArgs)]),
        ('non_ann_def', [('lack', 'non_ann_def', WithNonAnnArgs)]),
        ('non_ann_kw', [('lack', 'non_ann_kw', WithNonAnnArgs)]),
        ('non_ann_kw_def', [('lack', 'non_ann_kw_def', WithNonAnnArgs)]),
    ]


@pytest.mark.parametrize("full_final_kwargs", [[True], [False]])
def test_plan_no_args(full_final_kwargs):
    def fn():
        return True

    plan = andi.plan(fn, is_injectable=[], full_final_kwargs=full_final_kwargs)
    assert plan == [(fn, {})]
    assert plan.full_final_kwargs
    instances = build(plan)
    assert instances[fn]
    assert fn(**plan.final_kwargs(instances))


@pytest.mark.parametrize("full_final_kwargs", [[True], [False]])
def test_plan_use_fn_as_annotations(full_final_kwargs):
    def fn_ann(b: B):
        setattr(b, "modified", True)
        return b

    def fn(b: fn_ann):
        return b

    plan = andi.plan(fn, is_injectable=[fn_ann, B],
                     full_final_kwargs=full_final_kwargs)
    assert plan.full_final_kwargs
    instances = build(plan)
    assert instances[fn].modified


def test_class_or_func_str():
    assert _class_or_func_str(E) == "<class 'tests.test_plan.E'>.__init__()"
    fn_str = _class_or_func_str(test_class_or_func_str)
    assert fn_str.startswith("<function test_class_or_func_str")
    assert fn_str.endswith(">")


def test_error_messages():
    assert type(andi.andi._cyclic_dependency_error(E, [E,A,E])) == str
    assert type(andi.andi._argument_lacking_annotation_error('arg', E)) == str
    assert type(andi.andi._no_injectable_or_external_error('args', E, [A,E])) == str
    assert type(andi.andi._exception_msg(E, {
        'a': ['msg1', 'msg2'],
        'b': ['msg3', 'msg4'],
    })) == str