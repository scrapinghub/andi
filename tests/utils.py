from typing import Optional, Dict, Any, Callable, List

from andi import Step


def build(plan: List[Step], instances_stock: Optional[Dict[Callable, Any]] = None):
    """ Build instances dictionary from a plan """
    instances_stock = instances_stock or {}
    instances = {}
    for cls, kwargs_spec in plan:
        if cls in instances_stock:
            instances[cls] = instances_stock[cls]
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    return instances