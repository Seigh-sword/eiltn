#!/usr/bin/python3

from .lexer import tokenize
from .parser import parse
from .builder import build


def compile_source(src, name="<source>"):
    toks = tokenize(src, name)
    ast = parse(toks, name)
    return build(ast, name)
