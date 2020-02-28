import sys

import pytest

import andi


@pytest.mark.skipif(sys.version_info < (3, 6),
                    reason="Annotating the types of class variables require Python 3.6 or higher")
def test_attrs_str_type_annotations_py36():
    from tests.py36 import A_36, B_36
    assert andi.inspect(B_36.__init__) == {'a': [A_36]}
    assert andi.inspect(A_36.__init__) == {'b': [B_36]}


@pytest.mark.skipif(sys.version_info < (3, 7),
                    reason="'from __future__ import annotations' require Python 3.7 or higher")
def test_attrs_pep_563_forward_type_annotations_py37():
    from tests.py37_pep_563 import A_37, B_37
    assert andi.inspect(B_37.__init__) == {'a': [A_37]}
    assert andi.inspect(A_37.__init__) == {'b': [B_37]}
