from typing import Any, cast

from andi import Step
from andi.andi import CustomBuilder, PlanKey
from andi.typeutils import PlanCallable


def build(
    plan: list[Step],
    instances_stock: dict[PlanKey, Any] | None = None,
) -> dict[PlanCallable, Any]:
    """Build instances dictionary from a plan"""
    instances_stock = instances_stock or {}
    instances: dict[PlanCallable, Any] = {}
    for cls, kwargs_spec in plan:
        if cls in instances_stock:
            instances[cast("PlanCallable", cls)] = instances_stock[cls]
        elif isinstance(cls, CustomBuilder):
            instances[cls.result_class_or_fn] = cls.factory(
                **kwargs_spec.kwargs(instances)
            )
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    return instances
