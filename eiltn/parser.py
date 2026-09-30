from .errors import SyntaxErr
from .syntax import (
    Program, FnDef, Let, Set, Out, If, While, Return, ExprStmt,
    Lit, Var, Un, Bin, Call,
)

HEADER_ATTRS = ("threads",)


class Parser:
    def __init__(self, toks, name="<source>"):
        self.t = toks
        self.i = 0
        self.name = name

    def peek(self):
        return self.t[self.i]

    def advance(self):
        tok = self.t[self.i]
        self.i += 1
        return tok

    def fault(self, msg, tok=None):
        tok = tok or self.peek()
        raise SyntaxErr("%s:%d:%d: %s" % (self.name, tok.line, tok.col, msg))

    def expect(self, kind, value=None):
        tok = self.advance()
        if tok.kind != kind or (value is not None and tok.value != value):
            want = value if value is not None else kind
            self.fault("expected %s, found %r" % (want, tok.value), tok)
        return tok

    def at_op(self, value):
        tok = self.peek()
        return tok.kind == "op" and tok.value == value

    def at_kw(self, value):
        tok = self.peek()
        return tok.kind == "kw" and tok.value == value

    def skip_nl(self):
        while self.peek().kind == "nl":
            self.i += 1

    def parse(self):
        tok = self.peek()
        if tok.kind != "dir":
            self.fault("program must begin with the #bin/ header", tok)
        self.advance()
        attrs = {}
        while self.peek().kind == "ident":
            key_tok = self.advance()
            self.expect("op", "=")
            val_tok = self.expect("int")
            if key_tok.value not in HEADER_ATTRS:
                self.fault("unknown header attribute %r (allowed: %s)"
                           % (key_tok.value, ", ".join(HEADER_ATTRS)), key_tok)
            attrs[key_tok.value] = val_tok.value
        self.skip_nl()
        funcs = []
        while self.peek().kind != "eof":
            funcs.append(self.fn_def())
            self.skip_nl()
        if not funcs:
            self.fault("program defines no functions")
        return Program(attrs, funcs)

    def fn_def(self):
        tok = self.expect("kw", "fn")
        name = self.expect("ident").value
        self.expect("op", "(")
        params = []
        if self.peek().kind == "ident":
            params.append(self.advance().value)
            while self.at_op(","):
                self.advance()
                ptok = self.expect("ident")
                if ptok.value in params:
                    self.fault("duplicate parameter %r" % ptok.value, ptok)
                params.append(ptok.value)
        self.expect("op", ")")
        body = self.block()
        return FnDef(name, params, body, tok.line)

    def block(self):
        self.expect("op", "{")
        self.skip_nl()
        stmts = []
        while True:
            tok = self.peek()
            if tok.kind == "eof":
                self.fault("expected } before end of file", tok)
            if tok.kind == "op" and tok.value == "}":
                self.advance()
                return stmts
            stmts.append(self.stmt())
            self.skip_nl()

    def stmt(self):
        tok = self.peek()
        if tok.kind == "kw":
            w = tok.value
            if w == "let":
                self.advance()
                name = self.expect("ident").value
                self.expect("op", "=")
                e = self.expr()
                return Let(name, e, tok.line)
            if w == "set":
                self.advance()
                name = self.expect("ident").value
                self.expect("op", "=")
                e = self.expr()
                return Set(name, e, tok.line)
            if w == "out" or w == "err":
                self.advance()
                e = self.expr()
                return Out(e, tok.line, 0 if w == "out" else 1)
            if w == "if":
                return self.if_stmt()
            if w == "while":
                self.advance()
                cond = self.expr()
                body = self.block()
                return While(cond, body, tok.line)
            if w == "return":
                self.advance()
                t = self.peek()
                if t.kind == "nl" or (t.kind == "op" and t.value == "}"):
                    return Return(None, tok.line)
                return Return(self.expr(), tok.line)
            self.fault("unexpected keyword %r in statement position" % w, tok)
        e = self.expr()
        if not isinstance(e, Call):
            self.fault("statement must be let, set, out, err, if, while, return or a call", tok)
        return ExprStmt(e, tok.line)

    def if_stmt(self):
        tok = self.expect("kw", "if")
        cond = self.expr()
        then = self.block()
        els = None
        save = self.i
        self.skip_nl()
        if self.at_kw("else"):
            self.advance()
            if self.at_kw("if"):
                els = [self.if_stmt()]
            else:
                els = self.block()
        else:
            self.i = save
        return If(cond, then, els, tok.line)

    def expr(self):
        return self.or_expr()

    def or_expr(self):
        left = self.and_expr()
        while self.at_kw("or"):
            tok = self.advance()
            right = self.and_expr()
            left = Bin("or", left, right, tok.line)
        return left

    def and_expr(self):
        left = self.bit_or()
        while self.at_kw("and"):
            tok = self.advance()
            right = self.bit_or()
            left = Bin("and", left, right, tok.line)
        return left

    def bit_or(self):
        left = self.bit_xor()
        while self.at_op("|"):
            tok = self.advance()
            left = Bin("|", left, self.bit_xor(), tok.line)
        return left

    def bit_xor(self):
        left = self.bit_and()
        while self.at_op("^"):
            tok = self.advance()
            left = Bin("^", left, self.bit_and(), tok.line)
        return left

    def bit_and(self):
        left = self.equality()
        while self.at_op("&"):
            tok = self.advance()
            left = Bin("&", left, self.equality(), tok.line)
        return left

    def equality(self):
        left = self.compare()
        while self.at_op("==") or self.at_op("!="):
            tok = self.advance()
            left = Bin(tok.value, left, self.compare(), tok.line)
        return left

    def compare(self):
        left = self.shift()
        while self.at_op("<") or self.at_op("<=") or self.at_op(">") or self.at_op(">="):
            tok = self.advance()
            left = Bin(tok.value, left, self.shift(), tok.line)
        return left

    def shift(self):
        left = self.add()
        while self.at_op("<<") or self.at_op(">>"):
            tok = self.advance()
            left = Bin(tok.value, left, self.add(), tok.line)
        return left

    def add(self):
        left = self.mul()
        while self.at_op("+") or self.at_op("-"):
            tok = self.advance()
            left = Bin(tok.value, left, self.mul(), tok.line)
        return left

    def mul(self):
        left = self.unary()
        while self.at_op("*") or self.at_op("/") or self.at_op("%"):
            tok = self.advance()
            left = Bin(tok.value, left, self.unary(), tok.line)
        return left

    def unary(self):
        tok = self.peek()
        if tok.kind == "op" and tok.value in ("-", "~"):
            self.advance()
            return Un(tok.value, self.unary(), tok.line)
        if tok.kind == "kw" and tok.value == "not":
            self.advance()
            return Un("not", self.unary(), tok.line)
        return self.primary()

    def primary(self):
        tok = self.peek()
        if tok.kind == "int":
            self.advance()
            return Lit(tok.value, tok.line)
        if tok.kind == "str":
            self.advance()
            return Lit(tok.value, tok.line)
        if tok.kind == "kw" and tok.value in ("true", "false"):
            self.advance()
            return Lit(1 if tok.value == "true" else 0, tok.line)
        if tok.kind == "ident":
            self.advance()
            if self.at_op("("):
                self.advance()
                args = []
                if not self.at_op(")"):
                    args.append(self.expr())
                    while self.at_op(","):
                        self.advance()
                        args.append(self.expr())
                self.expect("op", ")")
                return Call(tok.value, args, tok.line)
            return Var(tok.value, tok.line)
        if tok.kind == "op" and tok.value == "(":
            self.advance()
            e = self.expr()
            self.expect("op", ")")
            return e
        self.fault("expected an expression, found %r" % (tok.value,), tok)


def parse(toks, name="<source>"):
    return Parser(toks, name).parse()
