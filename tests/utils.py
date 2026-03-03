from collections.abc import Callable
from typing import Any

from andi import Step
from andi.andi import CustomBuilder


def build(
    plan: list[Step],
    instances_stock: dict[Callable, Any] | None = None,
) -> dict[Callable, Any]:
    """Build instances dictionary from a plan"""
    instances_stock = instances_stock or {}
    instances = {}
    for cls, kwargs_spec in plan:
        if cls in instances_stock:
            instances[cls] = instances_stock[cls]
        elif isinstance(cls, CustomBuilder):
            instances[cls.result_class_or_fn] = cls.factory(
                **kwargs_spec.kwargs(instances)
            )
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    return instances
