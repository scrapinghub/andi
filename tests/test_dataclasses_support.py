import andi
from tests.types import ADCnp, BDCnp
from tests.types_pep563 import ADC, ADCStrRef, BDC


def test_dataclasses():
    assert andi.inspect(BDCnp.__init__) == {'a': [ADCnp]}


def test_dataclasses_forward_refs():
    assert andi.inspect(ADC.__init__) == {'b': [BDC]}
    assert andi.inspect(BDC.__init__) == {'a': [ADC]}
    assert andi.inspect(ADCnp.__init__) == {'b': [BDCnp]}


def test_dataclasses_py39_str_ref():
    assert andi.inspect(ADCStrRef.__init__) == {'b': [BDC]}
