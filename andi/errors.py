from collections.abc import Callable
from typing import NamedTuple


class NonProvidableError(TypeError):
    """Raised when a type is not providable"""

    def __init__(self, class_or_func, errors_per_argument):
        self.class_or_func = class_or_func
        self.errors_per_argument = errors_per_argument
        super().__init__(_exception_msg(class_or_func, errors_per_argument))


class CyclicDependencyErrCase(NamedTuple):
    class_or_func: Callable
    dependency_stack: list


class NonInjectableOrExternalErrCase(NamedTuple):
    argname: str
    class_or_func: Callable
    types: list[type | None]


class LackingAnnotationErrCase(NamedTuple):
    argname: str
    class_or_func: Callable


def _class_or_func_str(class_or_func):
    init_str = ".__init__()" if isinstance(class_or_func, type) else ""
    return f"{class_or_func}{init_str}"


def _cyclic_dependency_error(class_or_func, dependency_stack):
    return (
        f"Cyclic dependency found. Dependency graph: "
        f"{' -> '.join(map(str, [*dependency_stack, class_or_func]))}"
    )


def _no_injectable_or_external_error(argname, class_or_func, types):
    return (
        f"Any of {types} types are required "
        f"for argument '{argname}' "
        f"in '{_class_or_func_str(class_or_func)}' "
        f"but none of them is injectable or externally providable"
    )


def _argument_lacking_annotation_error(argname, class_or_func):
    return (
        f"Parameter '{argname}' is lacking annotations in "
        f"'{_class_or_func_str(class_or_func)}'"
    )


def _exception_msg(class_or_func, arg_errors):
    msg = ""
    for idx, (arg, errors) in enumerate(arg_errors.items()):
        if idx > 0:
            msg += "\n"
        msg += "Not possible to generate a plan for argument "
        msg += f"'{arg}' in '{_class_or_func_str(class_or_func)}'. "
        msg += "Causes:"
        for err_idx, err_case in enumerate(errors):
            if isinstance(err_case, CyclicDependencyErrCase):
                err_msg = _cyclic_dependency_error(*err_case)
            elif isinstance(err_case, NonInjectableOrExternalErrCase):
                err_msg = _no_injectable_or_external_error(*err_case)
            elif isinstance(err_case, LackingAnnotationErrCase):
                err_msg = _argument_lacking_annotation_error(*err_case)
            else:
                raise Exception("Unexpected type of error. This is a bug.")
            msg += f"\n    {err_idx}. {err_msg}"
    return msg
