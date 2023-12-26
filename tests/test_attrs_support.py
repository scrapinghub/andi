import andi

from tests.types import A_36, B_36
from tests.types_pep563 import A_37, B_37


def test_attrs_str_type_annotations():
    assert andi.inspect(B_36.__init__) == {'a': [A_36]}
    assert andi.inspect(A_36.__init__) == {'b': [B_36]}


def test_attrs_pep_563_forward_type_annotations():
    assert andi.inspect(B_37.__init__) == {'a': [A_37]}
    assert andi.inspect(A_37.__init__) == {'b': [B_37]}
