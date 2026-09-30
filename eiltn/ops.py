#!/usr/bin/python3

import math
import random
import sys
import time

from . import ein
from .errors import EINFault, ExitCode


def truthy(v):
    return ein.truthy(v)


def rt_fault(msg, line):
    raise TypeError("%s (line %d)" % (msg, line))


def _is_num(v):
    return isinstance(v, (int, float))


def rt_add(p, q, line):
    if isinstance(p, int):
        if isinstance(q, int):
            return ein.word(p + q)
        if isinstance(q, float):
            return p + q
    elif isinstance(p, float):
        if _is_num(q):
            return p + q
    elif isinstance(p, str):
        if isinstance(q, str):
            return p + q
    rt_fault("type fault: + expects two numbers or two strings", line)


def rt_sub(p, q, line):
    if not _is_num(p) or not _is_num(q):
        rt_fault("type fault: - expects numbers", line)
    if isinstance(p, int) and isinstance(q, int):
        return ein.word(p - q)
    return p - q


def rt_mul(p, q, line):
    if not _is_num(p) or not _is_num(q):
        rt_fault("type fault: * expects numbers", line)
    if isinstance(p, int) and isinstance(q, int):
        return ein.word(p * q)
    return p * q


def rt_div(p, q, line):
    if not _is_num(p) or not _is_num(q):
        rt_fault("type fault: / expects numbers", line)
    if isinstance(p, int) and isinstance(q, int):
        if q == 0:
            raise ZeroDivisionError("division by zero")
        r = abs(p) // abs(q)
        if (p < 0) != (q < 0):
            r = -r
        return ein.word(r)
    if q == 0.0:
        raise ZeroDivisionError("division by zero")
    return p / q


def rt_mod(p, q, line):
    if not isinstance(p, int) or not isinstance(q, int):
        rt_fault("type fault: %% expects integer words; use fmod() for floats", line)
    if q == 0:
        raise ZeroDivisionError("modulo by zero")
    r = abs(p) % abs(q)
    return -r if p < 0 else r


def rt_bit(p, q, line, name):
    if not isinstance(p, int) or not isinstance(q, int):
        rt_fault("type fault: %s expects integer words" % name, line)
    return True


def rt_bit1(p, line, name):
    if not isinstance(p, int):
        rt_fault("type fault: %s expects an integer word" % name, line)
    return True


def rt_neg(p, line):
    if isinstance(p, int):
        return ein.word(-p)
    if isinstance(p, float):
        return -p
    rt_fault("type fault: negate expects a number", line)


def rt_ord_cmp(p, q, line, name):
    ps = isinstance(p, str)
    qs = isinstance(q, str)
    if ps != qs:
        rt_fault("type fault: %s cannot order a string against a number" % name, line)
    return True


def printf(channel, v, args, line):
    if not isinstance(v, str):
        rt_fault("type fault: printf expects a format string", line)
    try:
        out = v % tuple(args)
    except TypeError as e:
        rt_fault("printf format error: %s" % e, line)
    except ValueError as e:
        rt_fault("printf format error: %s" % e, line)
    w = sys.stdout if channel == 0 else sys.stderr
    w.write(out)


def native(idx, args, line, ctx=None):
    name = ein.NATIVES[idx]
    if name == "clock":
        return ein.word(time.perf_counter_ns())
    if name == "rand":
        return random.random()
    if name == "randint":
        a, b = args
        if not isinstance(a, int) or not isinstance(b, int):
            rt_fault("type fault: randint expects two integer words", line)
        if a > b:
            rt_fault("randint expects lo <= hi", line)
        return random.randint(a, b)
    if name == "sqrt":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: sqrt expects a number", line)
        if a < 0:
            return float("nan")
        return math.sqrt(a)
    if name == "pow":
        a, b = args
        if not _is_num(a) or not _is_num(b):
            rt_fault("type fault: pow expects numbers", line)
        return math.pow(a, b)
    if name == "floor":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: floor expects a number", line)
        return ein.word(math.floor(a))
    if name == "ceil":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: ceil expects a number", line)
        return ein.word(math.ceil(a))
    if name == "round":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: round expects a number", line)
        r = math.floor(a + 0.5) if a >= 0 else math.ceil(a - 0.5)
        return ein.word(r)
    if name == "sin":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: sin expects a number", line)
        return math.sin(a)
    if name == "cos":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: cos expects a number", line)
        return math.cos(a)
    if name == "tan":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: tan expects a number", line)
        return math.tan(a)
    if name == "log":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: log expects a number", line)
        if a <= 0:
            rt_fault("log expects a positive number", line)
        return math.log(a)
    if name == "exp":
        a = args[0]
        if not _is_num(a):
            rt_fault("type fault: exp expects a number", line)
        return math.exp(a)
    if name == "abs":
        a = args[0]
        if isinstance(a, int):
            return ein.word(abs(a))
        if isinstance(a, float):
            return abs(a)
        rt_fault("type fault: abs expects a number", line)
    if name == "fmod":
        a, b = args
        if not _is_num(a) or not _is_num(b):
            rt_fault("type fault: fmod expects numbers", line)
        if b == 0:
            raise ZeroDivisionError("fmod by zero")
        return math.fmod(a, b)
    if name == "len":
        a = args[0]
        if isinstance(a, str):
            return len(a)
        rt_fault("type fault: len expects a string", line)
    if name == "substr":
        s, i, j = args
        if not isinstance(s, str) or not isinstance(i, int) or not isinstance(j, int):
            rt_fault("type fault: substr expects a string and two words", line)
        if i < 0 or j > len(s) or i > j:
            rt_fault("substr range %d..%d outside string of length %d" % (i, j, len(s)), line)
        return s[i:j]
    if name == "upper":
        a = args[0]
        if not isinstance(a, str):
            rt_fault("type fault: upper expects a string", line)
        return a.upper()
    if name == "lower":
        a = args[0]
        if not isinstance(a, str):
            rt_fault("type fault: lower expects a string", line)
        return a.lower()
    if name == "trim":
        a = args[0]
        if not isinstance(a, str):
            rt_fault("type fault: trim expects a string", line)
        return a.strip()
    if name == "contains":
        a, b = args
        if not isinstance(a, str) or not isinstance(b, str):
            rt_fault("type fault: contains expects two strings", line)
        return 1 if b in a else 0
    if name == "index":
        a, b = args
        if not isinstance(a, str) or not isinstance(b, str):
            rt_fault("type fault: index expects two strings", line)
        return a.find(b)
    if name == "replace":
        a, b, c = args
        if not isinstance(a, str) or not isinstance(b, str) or not isinstance(c, str):
            rt_fault("type fault: replace expects three strings", line)
        return a.replace(b, c)
    if name == "repeat":
        a, b = args
        if not isinstance(a, str) or not isinstance(b, int):
            rt_fault("type fault: repeat expects a string and a word", line)
        if b < 0:
            rt_fault("repeat expects a non-negative count", line)
        return a * b
    if name == "reverse":
        a = args[0]
        if not isinstance(a, str):
            rt_fault("type fault: reverse expects a string", line)
        return a[::-1]
    if name == "str":
        return ein.fmt(args[0])
    if name == "num":
        a = args[0]
        if isinstance(a, int) or isinstance(a, float):
            return a
        if isinstance(a, str):
            t = a.strip()
            try:
                return ein.word(int(t, 10))
            except ValueError:
                pass
            try:
                return float(t)
            except ValueError:
                rt_fault("num cannot parse %r" % a, line)
        rt_fault("type fault: num expects a string or number", line)
    if name == "int":
        a = args[0]
        if isinstance(a, int):
            return a
        if isinstance(a, float):
            return ein.word(int(a))
        if isinstance(a, str):
            try:
                return ein.word(int(a.strip(), 10))
            except ValueError:
                rt_fault("int cannot parse %r" % a, line)
        rt_fault("type fault: int expects a number or string", line)
    if name == "float":
        a = args[0]
        if isinstance(a, (int, float)):
            return float(a)
        if isinstance(a, str):
            try:
                return float(a.strip())
            except ValueError:
                rt_fault("float cannot parse %r" % a, line)
        rt_fault("type fault: float expects a number or string", line)
    if name == "hex":
        a = args[0]
        if not isinstance(a, int):
            rt_fault("type fault: hex expects an integer word", line)
        return "0x" + format(a & ein.WORD_MASK, "x")
    if name == "bin":
        a = args[0]
        if not isinstance(a, int):
            rt_fault("type fault: bin expects an integer word", line)
        return "0b" + format(a & ein.WORD_MASK, "b")
    if name == "chr":
        a = args[0]
        if not isinstance(a, int) or not 0 <= a <= 0x10FFFF:
            rt_fault("type fault: chr expects a word in 0..0x10FFFF", line)
        return chr(a)
    if name == "ord":
        a = args[0]
        if isinstance(a, str) and len(a) > 0:
            return ord(a[0])
        rt_fault("type fault: ord expects a non-empty string", line)
    if name == "exit":
        a = args[0]
        if not isinstance(a, int):
            rt_fault("type fault: exit expects an integer word", line)
        raise ExitCode(a)
    if name == "argc":
        return len(ctx.args) if ctx is not None else 0
    if name == "argv":
        a = args[0]
        if not isinstance(a, int):
            rt_fault("type fault: argv expects an integer word", line)
        if ctx is None or a < 0 or a >= len(ctx.args):
            return ""
        return ctx.args[a]
    raise EINFault("internal: unknown native %d" % idx)
