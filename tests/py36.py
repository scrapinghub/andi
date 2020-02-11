import attr

import andi


@attr.s(auto_attribs=True)
class A_36:
    b: 'B_36'


@attr.s(auto_attribs=True)
class B_36:
    a: A_36


def cross_referenced_within_func():

    @attr.s(auto_attribs=True)
    class A:
        b: 'B'

    @attr.s(auto_attribs=True)
    class B:
        a: A

    return andi.inspect(A.__init__), andi.inspect(B.__init__)