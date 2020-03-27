# -*- coding: utf-8 -*-
from collections import namedtuple


class NonProvidableError(TypeError):
    """ Raised when a type is not providable """

    def __init__(self, class_or_func, errors_per_argument):
        self.class_or_func = class_or_func
        self.errors_per_argument = errors_per_argument
        super().__init__(_exception_msg(class_or_func, errors_per_argument))


CyclicDependencyErrCase = namedtuple("CyclicDependencyErrCase",
                                     "class_or_func,dependency_stack")
NonInjectableOrExternalErrCase = namedtuple("NonInjectableOrExternalErrCase",
                                            "argname,class_or_func,types")
LackingAnnotationErrCase = namedtuple("LackingAnnotationErrCase",
                                      "argname, class_or_func")


def _class_or_func_str(class_or_func):
    init_str = ".__init__()" if isinstance(class_or_func, type) else ""
    return "{}{}".format(class_or_func, init_str)


def _cyclic_dependency_error(class_or_func, dependency_stack):
    error = "Cyclic dependency found. Dependency graph: {}".format(
        " -> ".join(map(str, dependency_stack + [class_or_func])))
    return error


def _no_injectable_or_external_error(argname, class_or_func, types):
    msg = "Any of {} types are required ".format(types)
    msg += "for argument '{}' ".format(argname)
    msg += "in '{}' ".format(_class_or_func_str(class_or_func))
    msg += "but none of them is injectable or externally providable"
    return msg


def _argument_lacking_annotation_error(argname, class_or_func):
    msg = "Parameter '{}' is lacking annotations in " \
          "'{}'".format(
        argname, _class_or_func_str(class_or_func))
    return msg


def _exception_msg(class_or_func, arg_errors):
    msg = ""
    for idx, (arg, errors) in enumerate(arg_errors.items()):
        if idx > 0:
            msg += "\n"
        msg += "Not possible to generate a plan for argument "
        msg += "'{}' in '{}'. ".format(arg, _class_or_func_str(class_or_func))
        msg += "Causes:"
        for idx, err_case in enumerate(errors):
            if type(err_case) == CyclicDependencyErrCase:
                err_msg = _cyclic_dependency_error(*err_case)
            elif type(err_case) == NonInjectableOrExternalErrCase:
                err_msg = _no_injectable_or_external_error(*err_case)
            elif type(err_case) == LackingAnnotationErrCase:
                err_msg = _argument_lacking_annotation_error(*err_case)
            else:
                raise Exception("Unexpected type of error. This is a bug.")
            msg += "\n    {}. {}".format(idx, err_msg)
    return msg
