import time

from . import ein
from .errors import EINFault


def add(a, b):
    if isinstance(a, int):
        if isinstance(b, int):
            return ein.word(a + b)
    elif isinstance(a, str):
        if isinstance(b, str):
            return a + b
    raise TypeError("type fault: + expects two words or two strings")


def compare_eq(a, b, want_eq, x):
    if isinstance(a, int) != isinstance(b, int):
        return 0 if want_eq else 1
    r = a == b
    return 1 if r == want_eq else 0


def compare_ord(a, b, x, mode):
    ok = False
    if isinstance(a, int) and isinstance(b, int):
        ok = True
    elif isinstance(a, str) and isinstance(b, str):
        ok = True
    if not ok:
        raise TypeError("type fault: ordering expects two words or two strings")
    if mode == 0:
        return 1 if a < b else 0
    if mode == 1:
        return 1 if a <= b else 0
    if mode == 2:
        return 1 if a > b else 0
    return 1 if a >= b else 0


def _typefault(name, x):
    raise TypeError("type fault: %s expects machine words" % name)


def _int1(a, name, x):
    if not isinstance(a, int):
        _typefault(name, x)


def _int2(a, b, name, x):
    if not isinstance(a, int) or not isinstance(b, int):
        _typefault(name, x)


def native(idx, args, x):
    name = ein.NATIVES[idx]
    if name == "clock":
        return ein.word(time.perf_counter_ns())
    a = args[0]
    if name == "len":
        if isinstance(a, str):
            return len(a)
        raise TypeError("type fault: len expects a string")
    if name == "ord":
        if isinstance(a, str) and len(a) > 0:
            return ord(a[0])
        raise TypeError("type fault: ord expects a non-empty string")
    if name == "chr":
        if isinstance(a, int) and 0 <= a <= 0x10FFFF:
            return chr(a)
        raise TypeError("type fault: chr expects a word in 0..0x10FFFF")
    if name == "str":
        return ein.fmt(a)
    if name == "num":
        if isinstance(a, str):
            try:
                return ein.word(int(a.strip(), 10))
            except ValueError:
                raise TypeError("type fault: num cannot parse %r" % a)
        if isinstance(a, int):
            return a
        raise TypeError("type fault: num expects a string")
    if name == "abs":
        if isinstance(a, int):
            return ein.word(abs(a))
        raise TypeError("type fault: abs expects a word")
    if name == "hex":
        if isinstance(a, int):
            return "0x" + format(a & ein.WORD_MASK, "x")
        raise TypeError("type fault: hex expects a word")
    raise EINFault("internal: unknown native %d" % idx)
