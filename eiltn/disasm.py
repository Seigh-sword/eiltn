#!/usr/bin/python3

from . import ein


def _opnd(k, v, consts):
    if k == ein.K_CONST:
        c = consts[v] if v < len(consts) else "?"
        if isinstance(c, str):
            out = c.replace("\\", "\\\\").replace('"', '\\"')
            out = out.replace("\n", "\\n").replace("\t", "\\t").replace("\0", "\\0")
            return '#"%s"' % out
        return "#%r" % (c,)
    if k == ein.K_REG:
        return "r%d" % v
    if k == ein.K_CELL:
        return "m%d" % v
    return "-"


def _fmt_ins(x, prog):
    op = x.op
    ops = x.ops
    consts = prog.consts
    if op == ein.CONST:
        return "r%d <- %s" % (x.dst, _opnd(ops[0][0], ops[0][1], consts))
    if op == ein.LOAD:
        return "r%d <- %s" % (x.dst, _opnd(ops[0][0], ops[0][1], consts))
    if op == ein.STORE:
        return "m%d <- %s" % (x.aux, _opnd(ops[0][0], ops[0][1], consts))
    if op == ein.JMP:
        return ".b%d" % x.aux
    if op == ein.BR:
        return "%s ? .b%d : .b%d" % (_opnd(ops[0][0], ops[0][1], consts), x.aux, x.aux2)
    if op == ein.RET:
        if ops:
            return "%s" % _opnd(ops[0][0], ops[0][1], consts)
        return "#0"
    if op == ein.OUT:
        return "%s ->" % _opnd(ops[0][0], ops[0][1], consts)
    if op == ein.ERR:
        return "%s -> err" % _opnd(ops[0][0], ops[0][1], consts)
    if op == ein.PRINTF:
        args = ", ".join(_opnd(k, v, consts) for k, v in ops)
        return "%s -> %s" % (args, "out" if x.aux == 0 else "err")
    if op == ein.SELECT:
        return "r%d <- %s ? %s : %s" % (x.dst, _opnd(ops[0][0], ops[0][1], consts),
                                        _opnd(ops[1][0], ops[1][1], consts),
                                        _opnd(ops[2][0], ops[2][1], consts))
    if op == ein.CALL:
        fn = prog.funcs[x.aux]
        args = ", ".join(_opnd(k, v, consts) for k, v in ops)
        return "r%d <- %s(%s)" % (x.dst, fn.name, args)
    if op == ein.NATIVE:
        args = ", ".join(_opnd(k, v, consts) for k, v in ops)
        return "r%d <- %s(%s)" % (x.dst, ein.NATIVES[x.aux], args)
    if len(ops) == 2:
        return "r%d <- %s, %s" % (x.dst, _opnd(ops[0][0], ops[0][1], consts),
                                  _opnd(ops[1][0], ops[1][1], consts))
    if len(ops) == 1:
        return "r%d <- %s" % (x.dst, _opnd(ops[0][0], ops[0][1], consts))
    return "r%d" % x.dst


def text(prog):
    lines = []
    threads = prog.threads if prog.threads > 0 else "auto"
    lines.append("ein %s: consts=%d funcs=%d entry=%s threads=%s"
                 % (prog.name or "<program>", len(prog.consts), len(prog.funcs),
                    prog.funcs[prog.entry].name, threads))
    for i, c in enumerate(prog.consts):
        if isinstance(c, str):
            shown = c.replace("\\", "\\\\").replace('"', '\\"')
            shown = shown.replace("\n", "\\n").replace("\t", "\\t").replace("\0", "\\0")
            lines.append("  const #%-3d %s" % (i, '"%s"' % shown))
        else:
            lines.append("  const #%-3d %r" % (i, c))
    for f in prog.funcs:
        params = ", ".join("m%d" % i for i in range(f.arity))
        lines.append("")
        lines.append("fn %s(%s)  cells=%d regs=%d"
                     % (f.name, params, f.ncells, f.nregs))
        for blk in f.blocks:
            lines.append(".b%d:" % blk.index)
            for addr, x in enumerate(blk.ins):
                lines.append("  %04d  %-7s %-46s @%d"
                             % (addr, ein.OPNAMES[x.op], _fmt_ins(x, prog), x.line))
    return "\n".join(lines)
