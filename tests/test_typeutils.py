# -*- coding: utf-8 -*-
from typing import Union, Optional

from andi.typeutils import get_union_args


def test_get_union_args():
    assert get_union_args(Union[str, int]) == [str, int]


def test_get_union_args_optional():
    assert get_union_args(Optional[Union[str, int]]) == [str, int, None]
