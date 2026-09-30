#!/usr/bin/python3

import argparse
import sys
import time

from .api import compile_source
from . import binfmt
from .disasm import text as disassemble
from .dispatcher import Dispatch
from .errors import EiltnError

VERSION = "0.2.0"

SUBCOMMANDS = ("run", "build", "dis")


def _load_prog(path):
    if path.endswith(".ein"):
        prog = binfmt.load(path)
        how = "loaded ein binary"
    else:
        with open(path, "r", encoding="utf-8") as fh:
            src = fh.read()
        prog = compile_source(src, path)
        how = "built ein graph, jit ready"
    return prog, how


def cmd_run(a):
    t0 = time.perf_counter_ns()
    prog, how = _load_prog(a.file)
    t1 = time.perf_counter_ns()
    d = Dispatch(prog, threads=a.threads, stats=a.stats)
    rc = d.run(args=a.pargs)
    if a.stats:
        s = d.stats
        sys.stderr.write(
            "ein: %s in %.2f ms | %d nodes dispatched in %d waves, %d calls, %d worker threads, run %.2f ms\n"
            % (how, (t1 - t0) / 1e6, s.nodes, s.waves, s.calls, d.threads,
               s.nanos / 1e6))
    return rc


def cmd_build(a):
    with open(a.file, "r", encoding="utf-8") as fh:
        src = fh.read()
    prog = compile_source(src, a.file)
    out = a.out
    if out is None:
        base = a.file
        if base.endswith(".eil"):
            base = base[:-4]
        out = base + ".ein"
    data = binfmt.dump(prog)
    with open(out, "wb") as fh:
        fh.write(data)
    nodes = sum(len(b.ins) for f in prog.funcs for b in f.blocks)
    print("built %s: %d bytes, %d functions, %d ein nodes"
          % (out, len(data), len(prog.funcs), nodes))
    return 0


def cmd_dis(a):
    prog, _ = _load_prog(a.file)
    print(disassemble(prog))
    return 0


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    argv = list(argv)
    if argv and argv[0] not in SUBCOMMANDS and not argv[0].startswith("-"):
        argv.insert(0, "run")

    p = argparse.ArgumentParser(
        prog="eiltn",
        description="eiltn: jit-dispatched EIN node programs")
    p.add_argument("--version", action="version", version="eiltn " + VERSION)
    sub = p.add_subparsers(dest="cmd")

    r = sub.add_parser("run", help="run a .eil program (eiltn file.eil)")
    r.add_argument("file")
    r.add_argument("-t", "--threads", type=int, default=0,
                   help="worker threads for parallel call waves (0 = auto)")
    r.add_argument("-s", "--stats", action="store_true",
                   help="print ein dispatch statistics to stderr")
    r.add_argument("pargs", nargs=argparse.REMAINDER,
                   help="arguments passed to the program (argv)")

    b = sub.add_parser("build", help="compile a program to an ein binary")
    b.add_argument("file")
    b.add_argument("-o", "--out", help="output path (default: <name>.ein)")

    d = sub.add_parser("dis", help="disassemble a program or ein binary")
    d.add_argument("file")

    a = p.parse_args(argv)
    if a.cmd is None:
        p.print_usage(sys.stderr)
        return 2
    try:
        if a.cmd == "run":
            return cmd_run(a)
        if a.cmd == "build":
            return cmd_build(a)
        if a.cmd == "dis":
            return cmd_dis(a)
    except EiltnError as e:
        sys.stderr.write("error: %s\n" % e)
        return 1
    except OSError as e:
        sys.stderr.write("error: %s\n" % e)
        return 1
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 130
    return 2
