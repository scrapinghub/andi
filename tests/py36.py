from dataclasses import dataclass

import attr


@attr.s(auto_attribs=True)
class A_36:
    b: 'B_36'


@attr.s(auto_attribs=True)
class B_36:
    a: A_36


@dataclass
class ADC:
    b: 'BDC'


@dataclass
class BDC:
    a: ADC