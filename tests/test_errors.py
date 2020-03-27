import pytest

from andi.errors import CyclicDependencyErrCase, NonInjectableOrExternalErrCase, \
    LackingAnnotationErrCase, _class_or_func_str, _cyclic_dependency_error, \
    _argument_lacking_annotation_error, _no_injectable_or_external_error, \
    _exception_msg
from tests.test_plan import E, A


def test_error_messages():
    cyc = CyclicDependencyErrCase(E, [E, A, E])
    no_inj = NonInjectableOrExternalErrCase('args', E, [A,E])
    lack = LackingAnnotationErrCase('arg', E)
    assert type(_cyclic_dependency_error(*cyc)) == str
    assert type(_argument_lacking_annotation_error(*lack)) == str
    assert type(_no_injectable_or_external_error(*no_inj)) == str
    assert type(_exception_msg(E, {
        'a': [cyc, no_inj],
        'b': [lack, cyc],
    })) == str

    with pytest.raises(Exception):
        _exception_msg(E, {'arg': ('a', 'b')})


def test_class_or_func_str():
    assert _class_or_func_str(E) == "<class 'tests.test_plan.E'>.__init__()"
    fn_str = _class_or_func_str(test_class_or_func_str)
    assert fn_str.startswith("<function test_class_or_func_str")
    assert fn_str.endswith(">")