import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import ein
from .errors import EINFault
from .plan import bind_plan

try:
    _CPUS = os.cpu_count() or 1
except Exception:
    _CPUS = 1


class Sched:
    __slots__ = ("dep", "dependents", "ready0", "parallel")

    def __init__(self, dep, dependents, ready0, parallel):
        self.dep = dep
        self.dependents = dependents
        self.ready0 = ready0
        self.parallel = parallel


def build_schedule(blk):
    ins = blk.ins
    n = len(ins)
    dep = [0] * n
    dependents = [[] for _ in range(n)]
    producer = {}
    cell_loads = {}
    cell_stores = {}
    last_effect = None

    def link(i, j):
        dep[i] += 1
        dependents[j].append(i)

    for i, x in enumerate(ins):
        op = x.op
        for k, v in x.ops:
            if k == ein.K_REG:
                j = producer.get(v)
                if j is None or j >= i:
                    raise EINFault("internal: register r%d read before write" % v)
                link(i, j)
        if op == ein.STORE:
            c = x.aux
            j = cell_stores.get(c)
            if j is not None:
                link(i, j)
            for ld in cell_loads.get(c, ()):
                link(i, ld)
            cell_stores[c] = i
        elif op == ein.LOAD and x.ops[0][0] == ein.K_CELL:
            cell_loads.setdefault(x.ops[0][1], []).append(i)
        elif op == ein.OUT or op == ein.ERR or op == ein.NATIVE:
            if last_effect is not None:
                link(i, last_effect)
            last_effect = i
        if op != ein.JMP:
            producer[x.dst] = i
    term = ins[-1]
    if term.op in (ein.JMP, ein.BR, ein.RET) and last_effect is not None:
        link(n - 1, last_effect)

    dc = dep[:]
    wave = [i for i in range(n) if dc[i] == 0]
    call_waves = False
    drained = 0
    while wave:
        drained += len(wave)
        if sum(1 for i in wave if ins[i].op == ein.CALL) > 1:
            call_waves = True
        nxt = []
        for i in wave:
            for d in dependents[i]:
                dc[d] -= 1
                if dc[d] == 0:
                    nxt.append(d)
        wave = nxt
    if drained != n:
        raise EINFault("internal: dependency cycle in block %d" % blk.index)
    ready0 = [i for i in range(n) if dep[i] == 0]
    blk.sched = Sched(dep, dependents, ready0, call_waves)
    return blk.sched


class Stats:
    __slots__ = ("nodes", "waves", "calls", "nanos")

    def __init__(self):
        self.nodes = 0
        self.waves = 0
        self.calls = 0
        self.nanos = 0


class Frame:
    __slots__ = ("cells", "regs")

    def __init__(self, ncells, nregs):
        self.cells = [0] * ncells
        self.regs = [0] * nregs


class Dispatch:
    def __init__(self, prog, threads=0, stats=False):
        self.prog = prog
        t = threads if threads > 0 else prog.threads
        if t <= 0:
            t = min(8, _CPUS)
        self.threads = t
        self.pool = None
        self.stats = Stats() if stats else None
        self.depth = 0
        self.plans = {}

    def run(self):
        sys.setrecursionlimit(30000)
        if self.threads > 1:
            for size in (256 * 1024 * 1024, 64 * 1024 * 1024):
                try:
                    threading.stack_size(size)
                    break
                except (ValueError, RuntimeError, OverflowError):
                    continue
            self.pool = ThreadPoolExecutor(max_workers=self.threads)
        t0 = time.perf_counter_ns()
        try:
            self.call(self.prog.entry, [])
            return 0
        except EINFault as e:
            sys.stdout.flush()
            sys.stderr.write("EIN fault: %s\n" % e)
            return 1
        except RecursionError:
            sys.stdout.flush()
            sys.stderr.write("EIN fault: call depth exceeded\n")
            return 1
        finally:
            if self.pool is not None:
                self.pool.shutdown(wait=True)
                self.pool = None
            if self.stats is not None:
                self.stats.nanos = time.perf_counter_ns() - t0

    def call(self, fidx, args):
        fn = self.prog.funcs[fidx]
        if len(args) != fn.arity:
            raise EINFault("in %s: called with %d argument(s), expects %d"
                           % (fn.name, len(args), fn.arity))
        if self.stats is not None:
            self.stats.calls += 1
        frame = Frame(fn.ncells, fn.nregs)
        cells = frame.cells
        for i in range(len(args)):
            cells[i] = args[i]
        blocks = fn.blocks
        b = 0
        self.depth += 1
        try:
            while True:
                kind, v = self.block(blocks[b], fn, frame)
                if kind == "r":
                    return v
                b = v
        finally:
            self.depth -= 1

    def block(self, blk, fn, frame):
        ins = blk.ins
        n = len(ins)
        sched = blk.sched
        if sched is None:
            sched = build_schedule(blk)
        stats = self.stats
        if stats is not None:
            stats.nodes += n
        plan = self.plans.get(blk)
        if plan is None:
            plan = self.plans[blk] = bind_plan(blk, self.prog, self)
        use_pool = (self.pool is not None and self.depth == 0 and sched.parallel
                    and self.threads > 1)
        if not sched.parallel:
            if stats is not None:
                stats.waves += 1
            x = ins[0]
            try:
                for f, x in plan:
                    f(frame)
            except EINFault:
                raise
            except RecursionError:
                raise EINFault("in %s at line %d: call depth exceeded"
                               % (fn.name, x.line))
            except Exception as e:
                raise self.wrap(fn, x, e) from None
            return self.term(fn, frame, ins)
        dep = list(sched.dep)
        dependents = sched.dependents
        ready = list(sched.ready0)
        try:
            while ready:
                if stats is not None:
                    stats.waves += 1
                wave = ready
                ready = []
                if use_pool and len(wave) > 1:
                    futs = [(i, self.pool.submit(plan[i][0], frame)) for i in wave]
                    bad = None
                    for i, fut in futs:
                        e = fut.exception()
                        if e is not None and (bad is None or i < bad[0]):
                            bad = (i, e)
                    if bad is not None:
                        raise self.wrap(fn, plan[bad[0]][1], bad[1])
                else:
                    for i in wave:
                        f, x = plan[i]
                        try:
                            f(frame)
                        except EINFault:
                            raise
                        except Exception as e:
                            raise self.wrap(fn, x, e)
                for i in wave:
                    for d in dependents[i]:
                        dep[d] -= 1
                        if dep[d] == 0:
                            ready.append(d)
                ready.sort()
        except EINFault:
            raise
        except RecursionError:
            raise EINFault("in %s: call depth exceeded" % fn.name)
        return self.term(fn, frame, ins)

    def term(self, fn, frame, ins):
        t = ins[-1]
        op = t.op
        if op == ein.JMP:
            return ("j", t.aux)
        if op == ein.BR:
            c = self.value(t.ops[0], frame)
            return ("j", t.aux if ein.truthy(c) else t.aux2)
        return ("r", self.value(t.ops[0], frame) if t.ops else 0)

    def value(self, o, frame):
        k = o[0]
        if k == ein.K_REG:
            return frame.regs[o[1]]
        if k == ein.K_CONST:
            return self.prog.consts[o[1]]
        return frame.cells[o[1]]

    def wrap(self, fn, x, e):
        if isinstance(e, EINFault):
            return e
        if isinstance(e, ZeroDivisionError):
            msg = "division by zero"
        elif isinstance(e, RecursionError):
            msg = "call depth exceeded"
        else:
            msg = str(e) or type(e).__name__
        return EINFault("in fn %s at %s (line %d): %s"
                        % (fn.name, ein.OPNAMES[x.op], x.line, msg))


def run_program(prog, threads=0, stats=False):
    d = Dispatch(prog, threads=threads, stats=stats)
    rc = d.run()
    return rc, d.stats
