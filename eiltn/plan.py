import sys

from . import ein
from .errors import EINFault


def word(x):
    return ein.word(x)


def _reader(o, prog):
    k = o[0]
    if k == ein.K_CONST:
        v = prog.consts[o[1]]
        return lambda fr: v
    if k == ein.K_REG:
        i = o[1]
        return lambda fr: fr.regs[i]
    i = o[1]
    return lambda fr: fr.cells[i]


def bind_plan(blk, prog, disp):
    plan = []
    for x in blk.ins:
        if x.op in (ein.JMP, ein.BR, ein.RET):
            def f(fr):
                pass
            plan.append((f, x))
            continue
        plan.append((_bind(x, prog, disp), x))
    return plan


def _bind(x, prog, disp):
    op = x.op
    dst = x.dst

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
        w = sys.stdout if op == ein.OUT else sys.stderr
        k, s = x.ops[0]
        if k == ein.K_CONST:
            v = ein.fmt(prog.consts[s])
            def f(fr):
                w.write(v + "\n")
            return f
        def f(fr):
            w.write(ein.fmt(fr.regs[s]) + "\n")
        return f

    if op == ein.ADD:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            if isinstance(p, int):
                if isinstance(q, int):
                    p += q
                    p &= ein.WORD_MASK
                    fr.regs[dst] = p - (1 << 64) if p & ein.WORD_SIGN else p
                    return
            elif isinstance(p, str):
                if isinstance(q, str):
                    fr.regs[dst] = p + q
                    return
            raise TypeError("type fault: + expects two words or two strings")
        return f

    if op == ein.SUB:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            if not isinstance(p, int) or not isinstance(q, int):
                raise TypeError("type fault: SUB expects machine words")
            p -= q
            p &= ein.WORD_MASK
            fr.regs[dst] = p - (1 << 64) if p & ein.WORD_SIGN else p
        return f

    if op == ein.MUL:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            if not isinstance(p, int) or not isinstance(q, int):
                raise TypeError("type fault: MUL expects machine words")
            p *= q
            p &= ein.WORD_MASK
            fr.regs[dst] = p - (1 << 64) if p & ein.WORD_SIGN else p
        return f

    if op == ein.DIV:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            if not isinstance(p, int) or not isinstance(q, int):
                raise TypeError("type fault: DIV expects machine words")
            if q == 0:
                raise ZeroDivisionError("division by zero")
            r = abs(p) // abs(q)
            if (p < 0) != (q < 0):
                r = -r
            r &= ein.WORD_MASK
            fr.regs[dst] = r - (1 << 64) if r & ein.WORD_SIGN else r
        return f

    if op == ein.MOD:
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            if not isinstance(p, int) or not isinstance(q, int):
                raise TypeError("type fault: MOD expects machine words")
            if q == 0:
                raise ZeroDivisionError("division by zero")
            r = abs(p) % abs(q)
            if p < 0:
                r = -r
            fr.regs[dst] = r
        return f

    if op in (ein.BAND, ein.BOR, ein.BXOR):
        a, b = x.ops[0][1], x.ops[1][1]
        if op == ein.BAND:
            def f(fr):
                p = fr.regs[a]
                q = fr.regs[b]
                if not isinstance(p, int) or not isinstance(q, int):
                    raise TypeError("type fault: BAND expects machine words")
                fr.regs[dst] = ein.word(p & q)
        elif op == ein.BOR:
            def f(fr):
                p = fr.regs[a]
                q = fr.regs[b]
                if not isinstance(p, int) or not isinstance(q, int):
                    raise TypeError("type fault: BOR expects machine words")
                fr.regs[dst] = ein.word(p | q)
        else:
            def f(fr):
                p = fr.regs[a]
                q = fr.regs[b]
                if not isinstance(p, int) or not isinstance(q, int):
                    raise TypeError("type fault: BXOR expects machine words")
                fr.regs[dst] = ein.word(p ^ q)
        return f

    if op == ein.SHL or op == ein.SHR:
        a, b = x.ops[0][1], x.ops[1][1]
        if op == ein.SHL:
            def f(fr):
                p = fr.regs[a]
                q = fr.regs[b]
                if not isinstance(p, int) or not isinstance(q, int):
                    raise TypeError("type fault: SHL expects machine words")
                fr.regs[dst] = ein.word(p << (q & 63))
        else:
            def f(fr):
                p = fr.regs[a]
                q = fr.regs[b]
                if not isinstance(p, int) or not isinstance(q, int):
                    raise TypeError("type fault: SHR expects machine words")
                fr.regs[dst] = ein.word(p >> (q & 63))
        return f

    if op == ein.EQ or op == ein.NE:
        a, b = x.ops[0][1], x.ops[1][1]
        want = op == ein.EQ
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            if isinstance(p, int) != isinstance(q, int):
                fr.regs[dst] = 0 if want else 1
            else:
                r = p == q
                fr.regs[dst] = 1 if r == want else 0
        return f

    if op in (ein.LT, ein.LE, ein.GT, ein.GE):
        a, b = x.ops[0][1], x.ops[1][1]
        def f(fr):
            p = fr.regs[a]
            q = fr.regs[b]
            if op == ein.LT:
                r = p < q
            elif op == ein.LE:
                r = p <= q
            elif op == ein.GT:
                r = p > q
            else:
                r = p >= q
            fr.regs[dst] = 1 if r else 0
        return f

    if op == ein.AND or op == ein.OR:
        a, b = x.ops[0][1], x.ops[1][1]
        if op == ein.AND:
            def f(fr):
                r = fr.regs[a]
                s = fr.regs[b]
                fr.regs[dst] = 1 if (r != 0 if isinstance(r, int) else r != "") and (s != 0 if isinstance(s, int) else s != "") else 0
        else:
            def f(fr):
                r = fr.regs[a]
                s = fr.regs[b]
                fr.regs[dst] = 1 if (r != 0 if isinstance(r, int) else r != "") or (s != 0 if isinstance(s, int) else s != "") else 0
        return f

    if op == ein.NEG or op == ein.BNOT:
        a = x.ops[0][1]
        if op == ein.NEG:
            def f(fr):
                p = fr.regs[a]
                if not isinstance(p, int):
                    raise TypeError("type fault: NEG expects machine words")
                fr.regs[dst] = ein.word(-p)
        else:
            def f(fr):
                p = fr.regs[a]
                if not isinstance(p, int):
                    raise TypeError("type fault: BNOT expects machine words")
                fr.regs[dst] = ein.word(~p)
        return f

    if op == ein.NOT:
        a = x.ops[0][1]
        def f(fr):
            p = fr.regs[a]
            t = p != 0 if isinstance(p, int) else p != ""
            fr.regs[dst] = 0 if t else 1
        return f

    if op == ein.CALL:
        fidx = x.aux
        call = disp.call
        if all(o[0] == ein.K_REG for o in x.ops):
            args = tuple(o[1] for o in x.ops)
            def f(fr):
                fr.regs[dst] = call(fidx, [fr.regs[i] for i in args])
            return f
        readers = [_reader(o, prog) for o in x.ops]
        def f(fr):
            fr.regs[dst] = call(fidx, [r(fr) for r in readers])
        return f

    if op == ein.NATIVE:
        from .ops import native
        idx = x.aux
        if all(o[0] == ein.K_REG for o in x.ops):
            args = tuple(o[1] for o in x.ops)
            def f(fr):
                fr.regs[dst] = native(idx, [fr.regs[i] for i in args], x)
            return f
        readers = [_reader(o, prog) for o in x.ops]
        def f(fr):
            fr.regs[dst] = native(idx, [r(fr) for r in readers], x)
        return f

    raise EINFault_Wire("internal: cannot bind opcode %d" % op)


class EINFault_Wire(Exception):
    pass
