#!/usr/bin/python3

import struct

from . import ein
from .errors import LoadErr

MAGIC = b"EILN"
VERSION = 2


class _Reader:
    __slots__ = ("data", "off")

    def __init__(self, data):
        self.data = data
        self.off = 0

    def take(self, n, what):
        if self.off + n > len(self.data):
            raise LoadErr("truncated ein binary while reading %s" % what)
        b = self.data[self.off:self.off + n]
        self.off += n
        return b

    def u8(self, what):
        return self.take(1, what)[0]

    def u16(self, what):
        return struct.unpack("<H", self.take(2, what))[0]

    def u32(self, what):
        return struct.unpack("<I", self.take(4, what))[0]

    def i64(self, what):
        return struct.unpack("<q", self.take(8, what))[0]

    def f64(self, what):
        return struct.unpack("<d", self.take(8, what))[0]

    def raw(self, n, what):
        return self.take(n, what)


def dump(prog):
    out = bytearray()
    out += MAGIC
    out += struct.pack("<BBHHI", VERSION, 0, prog.threads & 0xFFFF, prog.entry,
                       len(prog.funcs))
    name_b = prog.name.encode("utf-8")
    out += struct.pack("<B", len(name_b))
    out += name_b
    out += struct.pack("<I", len(prog.consts))
    for c in prog.consts:
        if isinstance(c, str):
            b = c.encode("utf-8")
            out += struct.pack("<BI", 2, len(b))
            out += b
        elif isinstance(c, float):
            out += struct.pack("<Bd", 3, c)
        else:
            out += struct.pack("<Bq", 1, c)
    for f in prog.funcs:
        nb = f.name.encode("utf-8")
        if len(nb) > 255:
            raise LoadErr("function name too long: %s" % f.name)
        out += struct.pack("<B", len(nb))
        out += nb
        out += struct.pack("<BHHI", f.arity, f.ncells, f.nregs, len(f.blocks))
        for blk in f.blocks:
            out += struct.pack("<I", len(blk.ins))
            for x in blk.ins:
                out += struct.pack("<BHB", x.op, x.dst, len(x.ops))
                for k, v in x.ops:
                    out += struct.pack("<BH", k, v)
                out += struct.pack("<H", x.line)
                if x.op == ein.JMP:
                    out += struct.pack("<I", x.aux)
                elif x.op == ein.BR:
                    out += struct.pack("<II", x.aux, x.aux2)
                elif x.op == ein.CALL:
                    out += struct.pack("<H", x.aux)
                elif x.op == ein.NATIVE:
                    out += struct.pack("<B", x.aux)
                elif x.op == ein.STORE:
                    out += struct.pack("<H", x.aux)
                elif x.op == ein.PRINTF:
                    out += struct.pack("<B", x.aux)
    return bytes(out)


def parse(data, name="<ein>"):
    r = _Reader(data)
    if r.take(4, "magic") != MAGIC:
        raise LoadErr("%s is not an eiltn ein binary (bad magic)" % name)
    version = r.u8("version")
    if version != VERSION:
        raise LoadErr("unsupported ein binary version %d (expected %d)" % (version, VERSION))
    r.u8("flags")
    threads = r.u16("threads")
    entry = r.u16("entry")
    nfuncs = r.u32("func count")
    nl = r.u8("name length")
    prog_name = r.raw(nl, "program name").decode("utf-8", "replace")

    nconsts = r.u32("const count")
    consts = []
    for ci in range(nconsts):
        tag = r.u8("const tag")
        if tag == 1:
            consts.append(r.i64("const value"))
        elif tag == 2:
            slen = r.u32("string length")
            consts.append(r.raw(slen, "string bytes").decode("utf-8", "replace"))
        elif tag == 3:
            consts.append(r.f64("float value"))
        else:
            raise LoadErr("bad const tag %d at index %d" % (tag, ci))

    funcs = []
    for fi in range(nfuncs):
        if fi >= 65536:
            raise LoadErr("too many functions")
        fname_len = r.u8("fn name length")
        fname = r.raw(fname_len, "fn name").decode("utf-8", "replace")
        arity = r.u8("arity")
        ncells = r.u16("cells")
        nregs = r.u16("regs")
        nblocks = r.u32("block count")
        blocks = []
        for bi in range(nblocks):
            blk = ein.Block(bi)
            nins = r.u32("instruction count")
            for ii in range(nins):
                op = r.u8("opcode")
                if op not in ein.OPNAMES:
                    raise LoadErr("bad opcode %d in fn %s block %d inst %d"
                                  % (op, fname, bi, ii))
                dst = r.u16("dst")
                nops = r.u8("operand count")
                ops = []
                for oi in range(nops):
                    k = r.u8("operand kind")
                    if k not in (ein.K_CONST, ein.K_REG, ein.K_CELL):
                        raise LoadErr("bad operand kind %d in fn %s" % (k, fname))
                    v = r.u16("operand value")
                    if k == ein.K_CONST and v >= nconsts:
                        raise LoadErr("const index out of range in fn %s" % fname)
                    if k == ein.K_REG and v >= nregs:
                        raise LoadErr("register index out of range in fn %s" % fname)
                    if k == ein.K_CELL and v >= ncells:
                        raise LoadErr("cell index out of range in fn %s" % fname)
                    ops.append((k, v))
                line = r.u16("line")
                aux = 0
                aux2 = 0
                if op == ein.JMP:
                    aux = r.u32("jmp target")
                    if aux >= nblocks:
                        raise LoadErr("jump target out of range in fn %s" % fname)
                elif op == ein.BR:
                    aux = r.u32("branch target")
                    aux2 = r.u32("branch target")
                    if aux >= nblocks or aux2 >= nblocks:
                        raise LoadErr("branch target out of range in fn %s" % fname)
                elif op == ein.CALL:
                    aux = r.u16("call target")
                    if aux >= nfuncs:
                        raise LoadErr("call target out of range in fn %s" % fname)
                elif op == ein.NATIVE:
                    aux = r.u8("native index")
                    if aux >= len(ein.NATIVES):
                        raise LoadErr("native index out of range in fn %s" % fname)
                    if len(ops) != ein.NATIVE_ARITY[aux]:
                        raise LoadErr("native %s expects %d argument(s) in fn %s"
                                      % (ein.NATIVES[aux], ein.NATIVE_ARITY[aux], fname))
                elif op == ein.STORE:
                    aux = r.u16("store cell")
                    if aux >= ncells:
                        raise LoadErr("store cell out of range in fn %s" % fname)
                elif op == ein.PRINTF:
                    aux = r.u8("printf channel")
                    if aux not in (0, 1):
                        raise LoadErr("printf channel must be 0 or 1 in fn %s" % fname)
                    if not ops:
                        raise LoadErr("printf needs a format operand in fn %s" % fname)
                if not _check_shape(op, ops):
                    raise LoadErr("malformed operands for %s in fn %s (block %d inst %d)"
                                  % (ein.OPNAMES[op], fname, bi, ii))
                blk.ins.append(ein.Ins(op, dst, tuple(ops), aux, aux2, line))
            if not blk.ins:
                raise LoadErr("empty block %d in fn %s" % (bi, fname))
            if blk.ins[-1].op not in (ein.JMP, ein.BR, ein.RET):
                raise LoadErr("block %d in fn %s has no terminator" % (bi, fname))
            blocks.append(blk)
        funcs.append(ein.Func(fname, arity, ncells, nregs, blocks, fi))

    if entry >= nfuncs:
        raise LoadErr("entry index out of range")
    if funcs[entry].arity != 0:
        raise LoadErr("entry function %r must take no parameters" % funcs[entry].name)
    if r.off != len(data):
        raise LoadErr("trailing bytes after ein binary")
    return ein.Program(consts, funcs, entry, threads, prog_name)


def _check_shape(op, ops):
    kinds = tuple(k for k, _ in ops)
    n = len(ops)
    if op == ein.CONST:
        return n == 1 and kinds == (ein.K_CONST,)
    if op == ein.LOAD:
        return n == 1 and kinds == (ein.K_CELL,)
    if op == ein.STORE:
        return n == 1 and kinds == (ein.K_REG,)
    if op in (ein.ADD, ein.SUB, ein.MUL, ein.DIV, ein.MOD, ein.BAND, ein.BOR,
              ein.BXOR, ein.SHL, ein.SHR, ein.EQ, ein.NE, ein.LT, ein.LE,
              ein.GT, ein.GE, ein.AND, ein.OR):
        return n == 2 and kinds == (ein.K_REG, ein.K_REG)
    if op in (ein.NEG, ein.BNOT, ein.NOT):
        return n == 1 and kinds == (ein.K_REG,)
    if op == ein.SELECT:
        return n == 3 and kinds == (ein.K_REG, ein.K_REG, ein.K_REG)
    if op == ein.PRINTF:
        return n >= 1 and kinds[0] in (ein.K_REG, ein.K_CONST) \
            and all(k == ein.K_REG for k in kinds[1:])
    if op in (ein.OUT, ein.ERR):
        return n == 1 and kinds[0] in (ein.K_REG, ein.K_CONST)
    if op == ein.JMP:
        return n == 0
    if op == ein.BR:
        return n == 1 and kinds == (ein.K_REG,)
    if op == ein.RET:
        return n == 0 or (n == 1 and kinds[0] in (ein.K_REG, ein.K_CONST))
    if op in (ein.CALL, ein.NATIVE):
        return True
    return False


def load(path):
    with open(path, "rb") as fh:
        data = fh.read()
    return parse(data, path)


def save(path, prog):
    with open(path, "wb") as fh:
        fh.write(dump(prog))
