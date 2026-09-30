#!/usr/bin/python3

class Program:
    __slots__ = ("funcs",)

    def __init__(self, funcs):
        self.funcs = funcs


class FnDef:
    __slots__ = ("name", "params", "body", "line")

    def __init__(self, name, params, body, line):
        self.name = name
        self.params = params
        self.body = body
        self.line = line


class Let:
    __slots__ = ("name", "expr", "line")

    def __init__(self, name, expr, line):
        self.name = name
        self.expr = expr
        self.line = line


class Set:
    __slots__ = ("name", "expr", "line")

    def __init__(self, name, expr, line):
        self.name = name
        self.expr = expr
        self.line = line


class Out:
    __slots__ = ("expr", "line", "channel")

    def __init__(self, expr, line, channel):
        self.expr = expr
        self.line = line
        self.channel = channel


class If:
    __slots__ = ("cond", "then", "els", "line")

    def __init__(self, cond, then, els, line):
        self.cond = cond
        self.then = then
        self.els = els
        self.line = line


class While:
    __slots__ = ("cond", "body", "line")

    def __init__(self, cond, body, line):
        self.cond = cond
        self.body = body
        self.line = line


class For:
    __slots__ = ("init", "cond", "step", "body", "line")

    def __init__(self, init, cond, step, body, line):
        self.init = init
        self.cond = cond
        self.step = step
        self.body = body
        self.line = line


class Break:
    __slots__ = ("line",)

    def __init__(self, line):
        self.line = line


class Return:
    __slots__ = ("expr", "line")

    def __init__(self, expr, line):
        self.expr = expr
        self.line = line


class ExprStmt:
    __slots__ = ("call", "line")

    def __init__(self, call, line):
        self.call = call
        self.line = line


class Lit:
    __slots__ = ("value", "line")

    def __init__(self, value, line):
        self.value = value
        self.line = line


class Var:
    __slots__ = ("name", "line")

    def __init__(self, name, line):
        self.name = name
        self.line = line


class Un:
    __slots__ = ("op", "operand", "line")

    def __init__(self, op, operand, line):
        self.op = op
        self.operand = operand
        self.line = line


class Bin:
    __slots__ = ("op", "left", "right", "line")

    def __init__(self, op, left, right, line):
        self.op = op
        self.left = left
        self.right = right
        self.line = line


class Call:
    __slots__ = ("name", "args", "line")

    def __init__(self, name, args, line):
        self.name = name
        self.args = args
        self.line = line
