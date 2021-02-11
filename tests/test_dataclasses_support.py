import sys

import pytest

import andi


@pytest.mark.skipif(sys.version_info != (3, 6),
                    reason="Testing dataclasses backport for Python 3.6")
def test_dataclasses_py36():
    from tests.py36 import ADC, BDC
    assert andi.inspect(ADC.__init__) == {'b': [BDC]}
    assert andi.inspect(BDC.__init__) == {'a': [ADC]}


@pytest.mark.skipif(sys.version_info < (3, 7),
                    reason="Testing native dataclasses in Python 3.7 or higher")
def test_dataclasses_py37():
    from tests.py37 import ADCnp, BDCnp
    assert andi.inspect(BDCnp.__init__) == {'a': [ADCnp]}


@pytest.mark.skipif(sys.version_info < (3, 7, 6) or sys.version_info[:3] == (3, 8, 0),
                    reason="Dataclasses with forward references require "
                           "Python 3.7.6 or higher or Python 3.8.1 or higher")
def test_dataclasses_py37_forward_refs():
    from tests.py37_pep_563 import ADC, BDC
    assert andi.inspect(ADC.__init__) == {'b': [BDC]}
    assert andi.inspect(BDC.__init__) == {'a': [ADC]}
    from tests.py37 import ADCnp, BDCnp
    assert andi.inspect(ADCnp.__init__) == {'b': [BDCnp]}


@pytest.mark.skipif((sys.version_info < (3, 7, 6) or
                     sys.version_info[:3] == (3, 8, 0) or
                     sys.version_info >= (3, 9, 0)),
                    reason="Dataclasses with forward references require "
                           "Python 3.7.6 or higher or Python 3.8.1 or higher")
def test_dataclasses_py37_str_ref():
    """ String annotations are returned as ForwardRef when
    ``from __future__ import annotations`` is used. Just don declare them as string. """
    from typing import ForwardRef
    from tests.py37_pep_563 import ADCStrRef
    assert type(andi.inspect(ADCStrRef.__init__)['b'][0]) == ForwardRef


@pytest.mark.skipif(sys.version_info < (3, 9, 0),
                    reason="Dataclasses with string forward references in "
                           "Python >= 3.9 are resolved as types :-)")
def test_dataclasses_py39_str_ref():
    from tests.py37_pep_563 import ADCStrRef, BDC
    assert andi.inspect(ADCStrRef.__init__) == {'b': [BDC]}
