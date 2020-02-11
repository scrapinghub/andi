from __future__ import annotations

import attr


@attr.s(auto_attribs=True)
class A_37:
    b: B_37


@attr.s(auto_attribs=True)
class B_37:
    a: A_37
