import sys

import pytest

import andi


@pytest.mark.skipif(sys.version_info < (3, 6),
                    reason="Annotating the types of class variables require Python 3.6 or higher")
def test_attrs_str_type_annotations_py36():
    from py36 import A_36, B_36
    assert andi.inspect(B_36.__init__) == {'a': [A_36]}
    assert andi.inspect(A_36.__init__) == {'b': [B_36]}


@pytest.mark.skipif(sys.version_info < (3, 7),
                    reason="'from __future__ import annotations' require Python 3.7 or higher")
def test_attrs_str_type_annotations_py37():
    from py37 import A_37, B_37
    assert andi.inspect(B_37.__init__) == {'a': [A_37]}
    assert andi.inspect(A_37.__init__) == {'b': [B_37]}


@pytest.mark.skipif(sys.version_info < (3, 6),
                    reason="Annotating the types of class variables require Python 3.6 or higher")
@pytest.mark.xfail
def test_attrs_str_type_annotations_within_func_py36():
    """ Andi don't work with attrs classes defined within a function.
    More info at: https://github.com/python-attrs/attrs/issues/593#issuecomment-584632175"""
    from py36 import cross_referenced_within_func
    a_inspect, b_inspect = cross_referenced_within_func()
    assert b_inspect['a'].__name__ == 'A'
    assert a_inspect['b'].__name__ == 'B'
