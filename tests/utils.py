from typing import Optional, Dict, Any, Callable

from andi import PlanStepList


def build(plan: PlanStepList, instances_stock: Optional[Dict[Callable, Any]] = None):
    """ Build instances dictionary from a plan """
    instances_stock = instances_stock or {}
    instances = {}
    for cls, params in plan:
        if cls in instances_stock:
            instances[cls] = instances_stock[cls]
        else:
            kwargs = {param: instances[pcls]
                      for param, pcls in params.items()}
            instances[cls] = cls(**kwargs)
    return instances