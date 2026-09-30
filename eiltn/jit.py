#!/usr/bin/python3

import sys

from . import ein
from . import ops as rt
from .errors import EINFault


def generate(blk, prog):
    lines = ["def run(fr):"]
    lmap = [None]
    for x in blk.ins:
        if x.op in (ein.JMP, ein.BR, ein.RET):
            continue
        _emit(lines, lmap, x, prog)
    if len(lines) == 1:
        lines.append("    pass")
        lmap.append(None)
    return "\n".join(lines) + "\n", lmap


def _emit(lines, lmap, x, prog):
    op = x.op
    d = x.dst
    L = x.line

    def E(code):
        lines.append("    " + code)
        lmap.append((L, ein.OPNAMES[op]))

    def W(value):
        v = value
        v &= ein.WORD_MASK
        return "%d" % (v - (1 << 64)) if v & ein.WORD_SIGN else "%d" % v

    def RR(i):
        return "fr.regs[%d]" % i

    if op == ein.CONST:
        E("%s = %s" % (RR(d), _const_src(prog.consts[x.ops[0][1]])))
        return
    if op == ein.LOAD:
        E("%s = fr.cells[%d]" % (RR(d), x.ops[0][1]))
        return
    if op == ein.STORE:
        k, s = x.ops[0]
        v = "fr.regs[%d]" % s if k == ein.K_REG else _const_src(prog.consts[s])
        E("fr.cells[%d] = %s" % (x.aux, v))
        return
    if op == ein.OUT or op == ein.ERR:
        w = "so" if op == ein.OUT else "se"
        k, s = x.ops[0]
        if k == ein.K_CONST:
            E("%s.write(%s)" % (w, _const_src(ein.fmt(prog.consts[s]) + "\n")))
        else:
            E("%s.write(fmt(%s) + \"\\n\")" % (w, RR(s)))
        return
    if op == ein.PRINTF:
        w = "so" if x.aux == 0 else "se"
        k, s = x.ops[0]
        v = "fr.regs[%d]" % s if k == ein.K_REG else _const_src(prog.consts[s])
        E("v = %s" % v)
        E("if type(v) is not str:")
        E("    rt.rt_fault(\"type fault: printf expects a format string\", %d)" % L)
        if len(x.ops) > 1:
            args = ", ".join(RR(o[1]) for o in x.ops[1:])
            E("%s.write(v %% (%s,))" % (w, args))
        else:
            E("%s.write(v %% ())" % w)
        return
    if op == ein.SELECT:
        c = x.ops[0][1]
        a = x.ops[1][1]
        b = x.ops[2][1]
        E("%s = %s if %s else %s" % (RR(d), RR(a), RR(c), RR(b)))
        return
    if op == ein.ADD:
        a, b = x.ops[0][1], x.ops[1][1]
        E("p = %s" % RR(a))
        E("q = %s" % RR(b))
        E("if type(p) is int and type(q) is int:")
        E("    v = p + q")
        E("    v &= M")
        E("    %s = v - H if v & S else v" % RR(d))
        E("else:")
        E("    %s = rt.rt_add(p, q, %d)" % (RR(d), L))
        return
    if op == ein.SUB or op == ein.MUL:
        a, b = x.ops[0][1], x.ops[1][1]
        name = "rt_sub" if op == ein.SUB else "rt_mul"
        sym = "-" if op == ein.SUB else "*"
        E("p = %s" % RR(a))
        E("q = %s" % RR(b))
        E("if type(p) is int and type(q) is int:")
        E("    v = p %s q" % sym)
        E("    v &= M")
        E("    %s = v - H if v & S else v" % RR(d))
        E("else:")
        E("    %s = rt.%s(p, q, %d)" % (RR(d), name, L))
        return
    if op == ein.DIV:
        a, b = x.ops[0][1], x.ops[1][1]
        E("p = %s" % RR(a))
        E("q = %s" % RR(b))
        E("if type(p) is int and type(q) is int:")
        E("    if q == 0:")
        E("        raise ZeroDivisionError(\"division by zero\")")
        E("    v = abs(p) // abs(q)")
        E("    if (p < 0) != (q < 0):")
        E("        v = -v")
        E("    v &= M")
        E("    %s = v - H if v & S else v" % RR(d))
        E("else:")
        E("    %s = rt.rt_div(p, q, %d)" % (RR(d), L))
        return
    if op == ein.MOD:
        a, b = x.ops[0][1], x.ops[1][1]
        E("p = %s" % RR(a))
        E("q = %s" % RR(b))
        E("if type(p) is int and type(q) is int:")
        E("    if q == 0:")
        E("        raise ZeroDivisionError(\"modulo by zero\")")
        E("    v = abs(p) %% abs(q)")
        E("    %s = -v if p < 0 else v" % RR(d))
        E("else:")
        E("    %s = rt.rt_mod(p, q, %d)" % (RR(d), L))
        return
    if op in (ein.BAND, ein.BOR, ein.BXOR):
        a, b = x.ops[0][1], x.ops[1][1]
        sym = {"BAND": "&", "BOR": "|", "BXOR": "^"}[ein.OPNAMES[op]]
        E("p = %s" % RR(a))
        E("q = %s" % RR(b))
        E("if type(p) is int and type(q) is int:")
        E("    v = p %s q" % sym)
        E("    v &= M")
        E("    %s = v - H if v & S else v" % RR(d))
        E("else:")
        E("    rt.rt_bit(p, q, %d, \"%s\")" % (L, ein.OPNAMES[op]))
        E("    %s = 0" % RR(d))
        return
    if op == ein.SHL or op == ein.SHR:
        a, b = x.ops[0][1], x.ops[1][1]
        sym = "<<" if op == ein.SHL else ">>"
        E("p = %s" % RR(a))
        E("q = %s" % RR(b))
        E("if type(p) is int and type(q) is int:")
        E("    v = p %s (q & 63)" % sym)
        E("    v &= M")
        E("    %s = v - H if v & S else v" % RR(d))
        E("else:")
        E("    rt.rt_bit(p, q, %d, \"%s\")" % (L, ein.OPNAMES[op]))
        E("    %s = 0" % RR(d))
        return
    if op == ein.EQ or op == ein.NE:
        a, b = x.ops[0][1], x.ops[1][1]
        if op == ein.EQ:
            E("%s = 1 if %s == %s else 0" % (RR(d), RR(a), RR(b)))
        else:
            E("%s = 0 if %s == %s else 1" % (RR(d), RR(a), RR(b)))
        return
    if op in (ein.LT, ein.LE, ein.GT, ein.GE):
        a, b = x.ops[0][1], x.ops[1][1]
        sym = {ein.LT: "<", ein.LE: "<=", ein.GT: ">", ein.GE: ">="}[op]
        E("p = %s" % RR(a))
        E("q = %s" % RR(b))
        E("if (type(p) is str) != (type(q) is str):")
        E("    rt.rt_ord_cmp(p, q, %d, \"%s\")" % (L, ein.OPNAMES[op]))
        E("%s = 1 if p %s q else 0" % (RR(d), sym))
        return
    if op == ein.AND or op == ein.OR:
        a, b = x.ops[0][1], x.ops[1][1]
        link = "and" if op == ein.AND else "or"
        E("%s = 1 if rt.truthy(%s) %s rt.truthy(%s) else 0" % (RR(d), RR(a), link, RR(b)))
        return
    if op == ein.NOT:
        a = x.ops[0][1]
        E("%s = 0 if rt.truthy(%s) else 1" % (RR(d), RR(a)))
        return
    if op == ein.NEG:
        a = x.ops[0][1]
        E("p = %s" % RR(a))
        E("if type(p) is int:")
        E("    v = -p")
        E("    v &= M")
        E("    %s = v - H if v & S else v" % RR(d))
        E("else:")
        E("    %s = rt.rt_neg(p, %d)" % (RR(d), L))
        return
    if op == ein.BNOT:
        a = x.ops[0][1]
        E("p = %s" % RR(a))
        E("if type(p) is int:")
        E("    v = ~p")
        E("    v &= M")
        E("    %s = v - H if v & S else v" % RR(d))
        E("else:")
        E("    rt.rt_bit1(p, %d, \"BNOT\")" % L)
        E("    %s = 0" % RR(d))
        return
    if op == ein.CALL:
        args = ", ".join(RR(o[1]) for o in x.ops)
        E("%s = call(%d, [%s])" % (RR(d), x.aux, args))
        return
    if op == ein.NATIVE:
        args = ", ".join(RR(o[1]) for o in x.ops)
        E("%s = rt.native(%d, [%s], %d, ctx)" % (RR(d), x.aux, args, L))
        return
    raise EINFault("internal: jit cannot bind opcode %d" % op)


def _const_src(v):
    if isinstance(v, float) and v != v:
        return "float(\"nan\")"
    if isinstance(v, float) and v in (float("inf"), float("-inf")):
        return "float(\"%sinf\")" % ("-" if v < 0 else "")
    return repr(v)


def compile_block(blk, prog, disp):
    marker = "<eiltn-jit %s b%d>" % (prog.name or "program", blk.index)
    try:
        src, lmap = generate(blk, prog)
        code = compile(src, marker, "exec")
        g = {
            "M": ein.WORD_MASK,
            "S": ein.WORD_SIGN,
            "H": 1 << 64,
            "call": disp.call,
            "rt": rt,
            "fmt": ein.fmt,
            "so": sys.stdout,
            "se": sys.stderr,
            "ctx": disp,
        }
        exec(code, g)
        return g["run"], lmap, marker
    except SyntaxError:
        return None, None, marker
    except MemoryError:
        return None, None, marker


def jit_line_of(exc, marker, lmap):
    tb = exc.__traceback__
    ln = None
    while tb is not None:
        if tb.tb_frame.f_code.co_filename == marker:
            ln = tb.tb_lineno
        tb = tb.tb_next
    if ln is None or ln < 1 or ln > len(lmap):
        return None
    return lmap[ln - 1]


def _no_op(fr):
    pass


def closure_plan(blk, prog, disp):
    plan = []
    for x in blk.ins:
        if x.op in (ein.JMP, ein.BR, ein.RET):
            plan.append((_no_op, x))
            continue
        plan.append((_bind(x, prog, disp), x))
    return plan


def _bind(x, prog, disp):
    op = x.op
    dst = x.dst
    line = x.line
    native = rt.native
    call = disp.call
    ctx = disp

    if op == ein.CONST:
        v = prog.consts[x.ops[0][1]]
        def f(fr):
            fr.regs[dst] = v
        return f
    if op == ein.LOAD:
        c = x.ops[0][1]
        def f(fr):
            fr.regs[dst] = fr.cells[c]
        return f
    if op == ein.STORE:
        c = x.aux
        k, s = x.ops[0]
        if k == ein.K_REG:
            def f(fr):
                fr.cells[c] = fr.regs[s]
            return f
        v = prog.consts[s]
        def f(fr):
            fr.cells[c] = v
        return f
    if op == ein.OUT or op == ein.ERR:
        if op == ein.OUT:
            def f(fr):
                sys.stdout.write(ein.fmt(_val(x.ops[0], fr, prog)) + "\n")
        else:
            def f(fr):
                sys.stderr.write(ein.fmt(_val(x.ops[0], fr, prog)) + "\n")
        return f
    if op == ein.PRINTF:
        ch = x.aux
        def f(fr):
            v = _val(x.ops[0], fr, prog)
            rt.printf(ch, v, [_val(o, fr, prog) for o in x.ops[1:]], line)
        return f
    if op == ein.SELECT:
        c = x.ops[0][1]
        a = x.ops[1][1]
        b = x.ops[2][1]
        def f(fr):
            fr.regs[dst] = fr.regs[a] if rt.truthy(fr.regs[c]) else fr.regs[b]
        return f
    if op == ein.ADD:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = rt.rt_add(fr.regs[a], fr.regs[b], line)
        return f
    if op == ein.SUB:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = rt.rt_sub(fr.regs[a], fr.regs[b], line)
        return f
    if op == ein.MUL:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = rt.rt_mul(fr.regs[a], fr.regs[b], line)
        return f
    if op == ein.DIV:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = rt.rt_div(fr.regs[a], fr.regs[b], line)
        return f
    if op == ein.MOD:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = rt.rt_mod(fr.regs[a], fr.regs[b], line)
        return f
    if op == ein.BAND:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_bit(p, q, line, "BAND")
            fr.regs[dst] = ein.word(p & q)
        return f
    if op == ein.BOR:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_bit(p, q, line, "BOR")
            fr.regs[dst] = ein.word(p | q)
        return f
    if op == ein.BXOR:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_bit(p, q, line, "BXOR")
            fr.regs[dst] = ein.word(p ^ q)
        return f
    if op == ein.SHL:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_bit(p, q, line, "SHL")
            fr.regs[dst] = ein.word(p << (q & 63))
        return f
    if op == ein.SHR:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_bit(p, q, line, "SHR")
            fr.regs[dst] = ein.word(p >> (q & 63))
        return f
    if op == ein.EQ:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = 1 if fr.regs[a] == fr.regs[b] else 0
        return f
    if op == ein.NE:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = 0 if fr.regs[a] == fr.regs[b] else 1
        return f
    if op == ein.LT:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_ord_cmp(p, q, line, "LT")
            fr.regs[dst] = 1 if p < q else 0
        return f
    if op == ein.LE:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_ord_cmp(p, q, line, "LE")
            fr.regs[dst] = 1 if p <= q else 0
        return f
    if op == ein.GT:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_ord_cmp(p, q, line, "GT")
            fr.regs[dst] = 1 if p > q else 0
        return f
    if op == ein.GE:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            rt.rt_ord_cmp(p, q, line, "GE")
            fr.regs[dst] = 1 if p >= q else 0
        return f
    if op == ein.AND:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = 1 if rt.truthy(fr.regs[a]) and rt.truthy(fr.regs[b]) else 0
        return f
    if op == ein.OR:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            fr.regs[dst] = 1 if rt.truthy(fr.regs[a]) or rt.truthy(fr.regs[b]) else 0
        return f
    if op == ein.NOT:
        a = x.ops[0][1]
        def f(fr):
            fr.regs[dst] = 0 if rt.truthy(fr.regs[a]) else 1
        return f
    if op == ein.NEG:
        a = x.ops[0][1]
        def f(fr):
            fr.regs[dst] = rt.rt_neg(fr.regs[a], line)
        return f
    if op == ein.BNOT:
        a = x.ops[0][1]
        def f(fr):
            p = fr.regs[a]
            rt.rt_bit1(p, line, "BNOT")
            fr.regs[dst] = ein.word(~p)
        return f
    if op == ein.CALL:
        fidx = x.aux
        if all(o[0] == ein.K_REG for o in x.ops):
            args = tuple(o[1] for o in x.ops)
            def f(fr):
                fr.regs[dst] = call(fidx, [fr.regs[i] for i in args])
            return f
        def f(fr):
            fr.regs[dst] = call(fidx, [_val(o, fr, prog) for o in x.ops])
        return f
    if op == ein.NATIVE:
        idx = x.aux
        if all(o[0] == ein.K_REG for o in x.ops):
            args = tuple(o[1] for o in x.ops)
            def f(fr):
                fr.regs[dst] = native(idx, [fr.regs[i] for i in args], line, ctx)
            return f
        def f(fr):
            fr.regs[dst] = native(idx, [_val(o, fr, prog) for o in x.ops], line, ctx)
        return f
    raise EINFault("internal: cannot bind opcode %d" % op)


def _val(o, fr, prog):
    k = o[0]
    if k == ein.K_REG:
        return fr.regs[o[1]]
    if k == ein.K_CONST:
        return prog.consts[o[1]]
    return fr.cells[o[1]]
