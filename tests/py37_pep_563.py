from __future__ import annotations  # type: ignore

from dataclasses import dataclass

import attr


@attr.s(auto_attribs=True)
class A_37:
    b: B_37


@attr.s(auto_attribs=True)
class B_37:
    a: A_37


@dataclass
class ADC:
    b: BDC


@dataclass
class ADCStrRef:
    b: 'BDC'


@dataclass
class BDC:
    a: ADC