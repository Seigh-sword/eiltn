from .errors import SyntaxErr

KEYWORDS = frozenset((
    "fn", "let", "set", "out", "err", "if", "else", "while", "return",
    "true", "false", "and", "or", "not",
))

TWO_CHAR_OPS = frozenset(("<<", ">>", "==", "!=", "<=", ">="))
ONE_CHAR_OPS = frozenset("+-*/%&|^~<>=(){},")

HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
BIN_DIGITS = frozenset("01")

LITERAL_MAX = (1 << 64) - 1


class Token:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return "Token(%r, %r, %d:%d)" % (self.kind, self.value, self.line, self.col)


def tokenize(src, name="<source>"):
    toks = []
    i = 0
    line = 1
    col = 1
    n = len(src)
    saw_token = False

    def fault(msg, l=None, c=None):
        raise SyntaxErr("%s:%d:%d: %s" % (name, l if l is not None else line,
                                          c if c is not None else col, msg))

    while i < n:
        c = src[i]
        if c == "\n":
            if toks and toks[-1].kind != "nl":
                toks.append(Token("nl", "\n", line, col))
            i += 1
            line += 1
            col = 1
            continue
        if c in " \t\r":
            i += 1
            col += 1
            continue
        if c == "#":
            if not saw_token and src.startswith("#bin/", i):
                toks.append(Token("dir", "#bin/", line, col))
                saw_token = True
                i += 5
                col += 5
                continue
            fault("comments are not part of eiltn; only the #bin/ header is allowed")
        if c.isdigit():
            start = i
            if c == "0" and i + 1 < n and src[i + 1] in "xX":
                base = 16
                i += 2
                d = i
                while i < n and (src[i] in HEX_DIGITS or src[i] == "_"):
                    i += 1
                if i == d:
                    fault("invalid hex literal")
                text = src[d:i].replace("_", "")
                col += i - start
            elif c == "0" and i + 1 < n and src[i + 1] in "bB":
                base = 2
                i += 2
                d = i
                while i < n and (src[i] in BIN_DIGITS or src[i] == "_"):
                    i += 1
                if i == d:
                    fault("invalid binary literal")
                text = src[d:i].replace("_", "")
                col += i - start
            else:
                base = 10
                while i < n and (src[i].isdigit() or src[i] == "_"):
                    i += 1
                text = src[start:i].replace("_", "")
                col += i - start
            if i < n and (src[i].isalnum() or src[i] == "_"):
                fault("invalid number literal")
            val = int(text, base)
            if val > LITERAL_MAX:
                fault("integer literal exceeds 64 bits", line, col)
            if val >= (1 << 63):
                val -= 1 << 64
            toks.append(Token("int", val, line, col - (i - start)))
            saw_token = True
            continue
        if c.isalpha() or c == "_":
            start = i
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
            w = src[start:i]
            col += i - start
            if w in KEYWORDS:
                toks.append(Token("kw", w, line, col - (i - start)))
            else:
                toks.append(Token("ident", w, line, col - (i - start)))
            saw_token = True
            continue
        if c == '"':
            i += 1
            col += 1
            start_line = line
            start_col = col - 1
            buf = []
            while True:
                if i >= n or src[i] == "\n":
                    fault("unterminated string literal", start_line, start_col)
                ch = src[i]
                if ch == '"':
                    i += 1
                    col += 1
                    break
                if ch == "\\":
                    i += 1
                    col += 1
                    if i >= n or src[i] == "\n":
                        fault("unterminated string literal", start_line, start_col)
                    e = src[i]
                    if e == "n":
                        buf.append("\n")
                    elif e == "t":
                        buf.append("\t")
                    elif e == "r":
                        buf.append("\r")
                    elif e == "0":
                        buf.append("\0")
                    elif e == "\\":
                        buf.append("\\")
                    elif e == '"':
                        buf.append('"')
                    elif e == "x":
                        h = src[i + 1:i + 3]
                        if len(h) < 2 or h[0] not in HEX_DIGITS or h[1] not in HEX_DIGITS:
                            fault("invalid \\x escape")
                        buf.append(chr(int(h, 16)))
                        i += 2
                        col += 2
                    else:
                        fault("unknown escape \\%s" % e)
                    i += 1
                    col += 1
                    continue
                if ord(ch) < 32 or ord(ch) > 126:
                    fault("string literals accept printable ascii only; use \\xNN or chr() for other characters")
                buf.append(ch)
                i += 1
                col += 1
            toks.append(Token("str", "".join(buf), line, start_col))
            saw_token = True
            continue
        two = src[i:i + 2]
        if two in TWO_CHAR_OPS:
            toks.append(Token("op", two, line, col))
            i += 2
            col += 2
            saw_token = True
            continue
        if c in ONE_CHAR_OPS:
            toks.append(Token("op", c, line, col))
            i += 1
            col += 1
            saw_token = True
            continue
        if c == "!":
            fault("unexpected !; use not for logical negation")
        if ord(c) > 126 or ord(c) < 32:
            fault("unexpected character %r; eiltn source is plain ascii words, digits and operators" % c)
        fault("unexpected character %r" % c)

    toks.append(Token("eof", None, line, col))
    return toks
