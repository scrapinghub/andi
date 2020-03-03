from typing import Optional, Dict, Type, Any

from andi import Plan


def build(plan: Plan, instances_stock: Optional[Dict[Type, Any]] = None):
    """ Build instances dictionary from a plan """
    instances_stock = instances_stock or {}
    instances = {}
    for cls, params in plan.items():
        if cls in instances_stock:
            instances[cls] = instances_stock[cls]
        else:
            kwargs = {param: instances[pcls]
                      for param, pcls in params.items()}
            instances[cls] = cls(**kwargs)
    return instances