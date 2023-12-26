import sys
from typing import ForwardRef

import pytest

import andi
from tests.types import ADCnp, BDCnp
from tests.types_pep563 import ADC, ADCStrRef, BDC


def test_dataclasses():
    assert andi.inspect(BDCnp.__init__) == {'a': [ADCnp]}


def test_dataclasses_forward_refs():
    assert andi.inspect(ADC.__init__) == {'b': [BDC]}
    assert andi.inspect(BDC.__init__) == {'a': [ADC]}
    assert andi.inspect(ADCnp.__init__) == {'b': [BDCnp]}


@pytest.mark.skipif(sys.version_info >= (3, 9, 0),
                    reason="Tests pre-3.9 behavior of forward refs.")
def test_dataclasses_py37_str_ref():
    """ String annotations are returned as ForwardRef when
    ``from __future__ import annotations`` is used. Just don declare them as string. """
    assert type(andi.inspect(ADCStrRef.__init__)['b'][0]) == ForwardRef


@pytest.mark.skipif(sys.version_info < (3, 9, 0),
                    reason="Dataclasses with string forward references in "
                           "Python >= 3.9 are resolved as types :-)")
def test_dataclasses_py39_str_ref():
    assert andi.inspect(ADCStrRef.__init__) == {'b': [BDC]}
