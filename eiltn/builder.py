#!/usr/bin/python3

from . import ein
from .errors import BuildErr
from .syntax import (
    Let, Set, Out, If, While, For, Break, Return, ExprStmt,
    Lit, Var, Un, Bin, Call,
)

BIN_OPS = {
    "+": ein.ADD, "-": ein.SUB, "*": ein.MUL, "/": ein.DIV, "%": ein.MOD,
    "&": ein.BAND, "|": ein.BOR, "^": ein.BXOR, "<<": ein.SHL, ">>": ein.SHR,
    "==": ein.EQ, "!=": ein.NE, "<": ein.LT, "<=": ein.LE, ">": ein.GT, ">=": ein.GE,
    "and": ein.AND, "or": ein.OR,
}

UN_OPS = {"-": ein.NEG, "~": ein.BNOT, "not": ein.NOT}

IO_CHANNELS = {
    "println": 0,
    "out.println": 0,
    "err.println": 1,
    "out.printf": 0,
    "err.printf": 1,
}

DESUGARED = ("min", "max")


class Builder:
    def __init__(self, prog_ast, name="<source>"):
        self.ast = prog_ast
        self.name = name
        self.consts = []
        self.cmap = {}
        self.signatures = {}
        self.funcs = []

    def const_index(self, v):
        j = self.cmap.get(v)
        if j is None:
            j = len(self.consts)
            self.consts.append(v)
            self.cmap[v] = j
        return j

    def build(self):
        for idx, f in enumerate(self.ast.funcs):
            if f.name in self.signatures:
                raise BuildErr("%s:%d: function %r is defined twice" % (self.name, f.line, f.name))
            self.signatures[f.name] = (idx, len(f.params))
        if "main" not in self.signatures:
            raise BuildErr("%s: program has no main function" % self.name)
        entry, arity = self.signatures["main"]
        if arity != 0:
            raise BuildErr("%s: main must take no parameters" % self.name)
        for idx, f in enumerate(self.ast.funcs):
            self.funcs.append(FnCompiler(self, f, idx).run())
        return ein.Program(self.consts, self.funcs, entry, 0, self.name)


class FnCompiler:
    def __init__(self, builder, f, index):
        self.b = builder
        self.f = f
        self.index = index
        self.name = f.name
        self.arity = len(f.params)
        self.cells = {}
        for p in f.params:
            self.cells[p] = len(self.cells)
        self.nregs = 0
        self.blocks = [ein.Block(0)]
        self.cur = self.blocks[0].ins
        self.ver = {}
        self.done = False
        self.loop_exits = []

    def fault(self, msg, line):
        raise BuildErr("%s:%d: in fn %s: %s" % (self.b.name, line, self.name, msg))

    def reg(self):
        r = self.nregs
        self.nregs += 1
        return r

    def new_block(self):
        blk = ein.Block(len(self.blocks))
        self.blocks.append(blk)
        return blk.index

    def open(self, idx):
        self.cur = self.blocks[idx].ins
        self.ver = {}
        self.done = False

    def emit(self, op, dst, ops=(), aux=0, aux2=0, line=0):
        self.cur.append(ein.Ins(op, dst, tuple(ops), aux, aux2, line))

    def jmp(self, target, line):
        self.emit(ein.JMP, 0, (), target, 0, line)
        self.done = True

    def run(self):
        self.open(0)
        for s in self.f.body:
            self.stmt(s)
        if not self.done:
            self.emit(ein.RET, 0, ((ein.K_CONST, self.b.const_index(0)),), 0, 0, self.f.line)
        return ein.Func(self.name, self.arity, len(self.cells), self.nregs,
                        self.blocks, self.index)

    def stmt(self, s):
        if self.done:
            self.fault("unreachable statement after return, break or continue of loop", s.line)
        if isinstance(s, Let):
            if s.name in self.cells:
                self.fault("%r is already bound in this function; use set" % s.name, s.line)
            cell = len(self.cells)
            self.cells[s.name] = cell
            r = self.expr(s.expr)
            self.emit(ein.STORE, 0, ((ein.K_REG, r),), cell, 0, s.line)
            self.ver[cell] = r
        elif isinstance(s, Set):
            cell = self.cells.get(s.name)
            if cell is None:
                self.fault("%r is not bound; declare it with let" % s.name, s.line)
            r = self.expr(s.expr)
            self.emit(ein.STORE, 0, ((ein.K_REG, r),), cell, 0, s.line)
            self.ver[cell] = r
        elif isinstance(s, Out):
            o = self.operand(s.expr)
            self.emit(ein.OUT if s.channel == 0 else ein.ERR, 0, (o,), 0, 0, s.line)
        elif isinstance(s, Return):
            if s.expr is None:
                o = (ein.K_CONST, self.b.const_index(0))
            else:
                o = self.operand(s.expr)
            self.emit(ein.RET, 0, (o,), 0, 0, s.line)
            self.done = True
        elif isinstance(s, Break):
            if not self.loop_exits:
                self.fault("break outside of a loop", s.line)
            self.jmp(self.loop_exits[-1], s.line)
        elif isinstance(s, If):
            c = self.expr(s.cond)
            bt = self.new_block()
            bend = self.new_block()
            be = self.new_block() if s.els else bend
            self.emit(ein.BR, 0, ((ein.K_REG, c),), bt, be, s.line)
            self.done = True
            self.open(bt)
            for x in s.then:
                self.stmt(x)
            if not self.done:
                self.jmp(bend, s.line)
            if s.els:
                self.open(be)
                for x in s.els:
                    self.stmt(x)
                if not self.done:
                    self.jmp(bend, s.line)
            self.open(bend)
        elif isinstance(s, While):
            bc = self.new_block()
            self.jmp(bc, s.line)
            self.open(bc)
            c = self.expr(s.cond)
            bb = self.new_block()
            bx = self.new_block()
            self.emit(ein.BR, 0, ((ein.K_REG, c),), bb, bx, s.line)
            self.done = True
            self.loop_exits.append(bx)
            self.open(bb)
            for x in s.body:
                self.stmt(x)
            if not self.done:
                self.jmp(bc, s.line)
            self.loop_exits.pop()
            self.open(bx)
        elif isinstance(s, For):
            if s.init is not None:
                self.stmt(s.init)
                self.done = False
            bc = self.new_block()
            self.jmp(bc, s.line)
            self.open(bc)
            bb = self.new_block()
            bx = self.new_block()
            if s.cond is not None:
                c = self.expr(s.cond)
                self.emit(ein.BR, 0, ((ein.K_REG, c),), bb, bx, s.line)
            else:
                self.emit(ein.JMP, 0, (), bb, 0, s.line)
            self.done = True
            bs = self.new_block()
            self.loop_exits.append(bx)
            self.open(bb)
            for x in s.body:
                self.stmt(x)
            if not self.done:
                self.jmp(bs, s.line)
            self.open(bs)
            if s.step is not None:
                self.stmt(s.step)
                self.done = False
            self.emit(ein.JMP, 0, (), bc, 0, s.line)
            self.done = True
            self.loop_exits.pop()
            self.open(bx)
        elif isinstance(s, ExprStmt):
            self.expr(s.call)
        else:
            self.fault("unknown statement", s.line)

    def operand(self, e):
        if isinstance(e, Lit):
            return (ein.K_CONST, self.b.const_index(e.value))
        return (ein.K_REG, self.expr(e))

    def expr(self, e):
        if isinstance(e, Lit):
            r = self.reg()
            self.emit(ein.CONST, r, ((ein.K_CONST, self.b.const_index(e.value)),), 0, 0, e.line)
            return r
        if isinstance(e, Var):
            cell = self.cells.get(e.name)
            if cell is None:
                self.fault("%r is not bound in this function" % e.name, e.line)
            v = self.ver.get(cell)
            if v is not None:
                return v
            r = self.reg()
            self.emit(ein.LOAD, r, ((ein.K_CELL, cell),), 0, 0, e.line)
            self.ver[cell] = r
            return r
        if isinstance(e, Un):
            x = self.expr(e.operand)
            r = self.reg()
            self.emit(UN_OPS[e.op], r, ((ein.K_REG, x),), 0, 0, e.line)
            return r
        if isinstance(e, Bin):
            l = self.expr(e.left)
            r2 = self.expr(e.right)
            r = self.reg()
            self.emit(BIN_OPS[e.op], r, ((ein.K_REG, l), (ein.K_REG, r2)), 0, 0, e.line)
            return r
        if isinstance(e, Call):
            return self.call(e)
        self.fault("unknown expression", getattr(e, "line", 0))

    def io_call(self, e):
        channel = IO_CHANNELS[e.name]
        if e.name.endswith("println"):
            if len(e.args) != 1:
                self.fault("%s expects exactly 1 argument, got %d" % (e.name, len(e.args)), e.line)
            o = self.operand(e.args[0])
            self.emit(ein.OUT if channel == 0 else ein.ERR, 0, (o,), 0, 0, e.line)
            return 0
        if len(e.args) < 1:
            self.fault("%s expects a format string plus arguments" % e.name, e.line)
        fmtop = self.operand(e.args[0])
        argops = [(ein.K_REG, self.expr(a)) for a in e.args[1:]]
        self.emit(ein.PRINTF, 0, (fmtop,) + tuple(argops), channel, 0, e.line)
        return 0

    def desugar_minmax(self, e):
        want_min = e.name == "min"
        if len(e.args) != 2:
            self.fault("%s expects exactly 2 arguments, got %d" % (e.name, len(e.args)), e.line)
        l = self.expr(e.args[0])
        r2 = self.expr(e.args[1])
        c = self.reg()
        self.emit(ein.LT if want_min else ein.GT, c,
                  ((ein.K_REG, l), (ein.K_REG, r2)), 0, 0, e.line)
        d = self.reg()
        self.emit(ein.SELECT, d, ((ein.K_REG, c), (ein.K_REG, l), (ein.K_REG, r2)),
                  0, 0, e.line)
        return d

    def call(self, e):
        if e.name in IO_CHANNELS:
            return self.io_call(e)
        if e.name in DESUGARED:
            return self.desugar_minmax(e)
        sig = self.b.signatures.get(e.name)
        if sig is not None:
            idx, arity = sig
            if len(e.args) != arity:
                self.fault("fn %s expects %d argument(s), got %d"
                           % (e.name, arity, len(e.args)), e.line)
            argops = [(ein.K_REG, self.expr(a)) for a in e.args]
            r = self.reg()
            self.emit(ein.CALL, r, tuple(argops), idx, 0, e.line)
            return r
        if e.name in ein.NATIVES:
            want = ein.NATIVE_ARITY[ein.NATIVES.index(e.name)]
            if len(e.args) != want:
                self.fault("native %s expects %d argument(s), got %d"
                           % (e.name, want, len(e.args)), e.line)
            argops = [(ein.K_REG, self.expr(a)) for a in e.args]
            r = self.reg()
            self.emit(ein.NATIVE, r, tuple(argops), ein.NATIVES.index(e.name), 0, e.line)
            return r
        self.fault("unknown function %r" % e.name, e.line)


def build(prog_ast, name="<source>"):
    return Builder(prog_ast, name).build()
