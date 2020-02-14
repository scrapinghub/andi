from dataclasses import dataclass


@dataclass
class ADCnp:
    b: 'BDCnp'


@dataclass
class BDCnp:
    a: ADCnp