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
