import sys

import pytest

import andi


@pytest.mark.skipif(sys.version_info != (3, 6),
                    reason="Testing dataclasses backport for Python 3.6")
def test_dataclasses_py36():
    from py36 import ADC, BDC
    assert andi.inspect(ADC.__init__) == {'b': [BDC]}
    assert andi.inspect(BDC.__init__) == {'a': [ADC]}


@pytest.mark.skipif(sys.version_info < (3, 7),
                    reason="Dataclasses require Python 3.7 or higher")
def test_dataclasses_py37():
    from py37 import ADC, BDC
    assert andi.inspect(BDC.__init__) == {'a': [ADC]}
    from py37_no_pep_563 import ADCnp, BDCnp
    assert andi.inspect(BDCnp.__init__) == {'a': [ADCnp]}


@pytest.mark.skipif(sys.version_info < (3, 7, 6),
                    reason="Dataclasses with forward references require "
                           "Python 3.7.6 or higher")
def test_dataclasses_py37_forward_refs():
    from py37 import ADC, BDC
    assert andi.inspect(ADC.__init__) == {'b': [BDC]}
    from py37_no_pep_563 import ADCnp, BDCnp
    assert andi.inspect(ADCnp.__init__) == {'b': [BDCnp]}


@pytest.mark.skipif(sys.version_info < (3, 7),
                    reason="Dataclasses with forward references require "
                           "Python 3.7.6 or higher")
def test_dataclasses_py37_str_ref():
    """ String annotations are returned as ForwardRef when
    ``from __future__ import annotations`` is used. Just don declare them as string. """
    from typing import ForwardRef
    from py37 import ADCStrRef
    assert type(andi.inspect(ADCStrRef.__init__)['b'][0]) == ForwardRef