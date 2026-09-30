#!/usr/bin/python3

K_NONE = 0
K_CONST = 1
K_REG = 2
K_CELL = 3

CONST = 1
LOAD = 2
STORE = 3

ADD = 10
SUB = 11
MUL = 12
DIV = 13
MOD = 14
BAND = 15
BOR = 16
BXOR = 17
SHL = 18
SHR = 19

EQ = 20
NE = 21
LT = 22
LE = 23
GT = 24
GE = 25
AND = 26
OR = 27

NEG = 30
BNOT = 31
NOT = 32
SELECT = 33
PRINTF = 34

OUT = 40
ERR = 41

JMP = 50
BR = 51
RET = 52

CALL = 60
NATIVE = 61

OPNAMES = {
    CONST: "CONST",
    LOAD: "LOAD",
    STORE: "STORE",
    ADD: "ADD",
    SUB: "SUB",
    MUL: "MUL",
    DIV: "DIV",
    MOD: "MOD",
    BAND: "BAND",
    BOR: "BOR",
    BXOR: "BXOR",
    SHL: "SHL",
    SHR: "SHR",
    EQ: "EQ",
    NE: "NE",
    LT: "LT",
    LE: "LE",
    GT: "GT",
    GE: "GE",
    AND: "AND",
    OR: "OR",
    NEG: "NEG",
    BNOT: "BNOT",
    NOT: "NOT",
    SELECT: "SELECT",
    PRINTF: "PRINTF",
    OUT: "OUT",
    ERR: "ERR",
    JMP: "JMP",
    BR: "BR",
    RET: "RET",
    CALL: "CALL",
    NATIVE: "NATIVE",
}

NATIVES = (
    "clock", "rand", "randint", "sqrt", "pow", "floor", "ceil", "round",
    "sin", "cos", "tan", "log", "exp", "abs", "fmod",
    "len", "substr", "upper", "lower", "trim", "contains", "index",
    "replace", "repeat", "reverse",
    "str", "num", "int", "float", "hex", "bin", "chr", "ord",
    "exit", "argc", "argv",
)

NATIVE_ARITY = (
    0, 0, 2, 1, 2, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 2,
    1, 3, 1, 1, 1, 2, 2,
    3, 2, 1,
    1, 1, 1, 1, 1, 1, 1, 1,
    1, 0, 1,
)

WORD_MASK = (1 << 64) - 1
WORD_SIGN = 1 << 63
MIN_WORD = -(1 << 63)


def word(x):
    x &= WORD_MASK
    if x & WORD_SIGN:
        x -= 1 << 64
    return x


def truthy(v):
    if isinstance(v, int):
        return v != 0
    if isinstance(v, float):
        return v != 0.0
    return v != ""


def fmt(v):
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(v)
    return v


class Ins:
    __slots__ = ("op", "dst", "ops", "aux", "aux2", "line")

    def __init__(self, op, dst, ops, aux=0, aux2=0, line=0):
        self.op = op
        self.dst = dst
        self.ops = ops
        self.aux = aux
        self.aux2 = aux2
        self.line = line


class Block:
    __slots__ = ("index", "ins", "sched")

    def __init__(self, index):
        self.index = index
        self.ins = []
        self.sched = None


class Func:
    __slots__ = ("name", "arity", "ncells", "nregs", "blocks", "index")

    def __init__(self, name, arity, ncells, nregs, blocks, index):
        self.name = name
        self.arity = arity
        self.ncells = ncells
        self.nregs = nregs
        self.blocks = blocks
        self.index = index


class Program:
    __slots__ = ("consts", "funcs", "entry", "threads", "name")

    def __init__(self, consts, funcs, entry, threads, name=""):
        self.consts = consts
        self.funcs = funcs
        self.entry = entry
        self.threads = threads
        self.name = name
