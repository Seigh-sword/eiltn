#!/usr/bin/python3

class EiltnError(Exception):
    pass


class SyntaxErr(EiltnError):
    pass


class BuildErr(EiltnError):
    pass


class LoadErr(EiltnError):
    pass


class EINFault(Exception):
    pass


class ExitCode(EiltnError):
    def __init__(self, code):
        Exception.__init__(self, code)
        self.code = code
