from typing import Optional, Dict, Any, Callable, List

from andi import Step
from andi.andi import CustomBuilder


def build(plan: List[Step],
          instances_stock: Optional[Dict[Callable, Any]] = None,
          ) -> Dict[Callable, Any]:
    """ Build instances dictionary from a plan """
    instances_stock = instances_stock or {}
    instances = {}
    for cls, kwargs_spec in plan:
        if cls in instances_stock:
            instances[cls] = instances_stock[cls]
        elif isinstance(cls, CustomBuilder):
            instances[cls.result_class_or_fn] = cls.factory(**kwargs_spec.kwargs(instances))
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    return instances
