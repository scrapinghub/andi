from dataclasses import dataclass

import pytest

import andi


@dataclass
class A:
    e: 'E'


@dataclass
class B: pass


@dataclass
class C:
    a: A
    b: B


@dataclass
class D:
    a: A
    c: C


@dataclass
class E:
    b: B
    c: C
    d: D


def test_plan_and_build():
    plan = andi.plan(E, lambda x: True, [A])
    print(andi.plan_str(plan))
    instances = andi.build(plan, {A: ""})
    assert type(instances[E]) == E


def test_cyclic_dependency():
    with pytest.raises(TypeError):
        andi.plan(E, lambda x: True, [])
