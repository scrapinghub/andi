from typing import Optional, Dict, Any, Callable, List

from andi import Step


def build(plan: List[Step],
          instances_stock: Optional[Dict[Callable, Any]] = None,
          custom_builders: Optional[Dict[Callable, Callable]] = None,
          ) -> Dict[Callable, Any]:
    """ Build instances dictionary from a plan """
    instances_stock = instances_stock or {}
    custom_builders = custom_builders or {}
    instances = {}
    for cls, kwargs_spec in plan:
        if cls in instances_stock:
            instances[cls] = instances_stock[cls]
        elif cls in custom_builders:
            instances[cls] = custom_builders[cls](**kwargs_spec.kwargs(instances))
        else:
            instances[cls] = cls(**kwargs_spec.kwargs(instances))
    return instances
