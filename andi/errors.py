# -*- coding: utf-8 -*-
class NonProvidableError(TypeError):
    """ Raised when a type is not providable """


class CyclicDependencyError(TypeError):
    """ Raised on cyclic dependencies """

