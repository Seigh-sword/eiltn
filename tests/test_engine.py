import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout

from eiltn.api import compile_source
from eiltn import binfmt
from eiltn.dispatcher import run_program
from eiltn.errors import EiltnError


def run_src(src, threads=0, name="t.eil"):
    prog = compile_source(src, name)
    out = io.StringIO()
    with redirect_stdout(out):
        rc, _ = run_program(prog, threads=threads)
    return rc, out.getvalue()


def run_file(path, threads=0):
    prog = binfmt.load(path)
    out = io.StringIO()
    with redirect_stdout(out):
        rc, _ = run_program(prog, threads=threads)
    return rc, out.getvalue()


class TestEngine(unittest.TestCase):
    def test_hello(self):
        rc, out = run_src('#bin/\nfn main() { out "hello"\n out "world" }\n')
        self.assertEqual(rc, 0)
        self.assertEqual(out, "hello\nworld\n")

    def test_arithmetic_and_words(self):
        rc, out = run_src(
            "#bin/\nfn main() {\n"
            "    out 7 / 2\n"
            "    out (0 - 7) / 2\n"
            "    out (0 - 7) % 2\n"
            "    out 1 << 63\n"
            "    out ~0\n"
            "}\n")
        self.assertEqual(out, "3\n-3\n-1\n-9223372036854775808\n-1\n")

    def test_wraparound(self):
        rc, out = run_src(
            "#bin/\nfn main() {\n"
            "    let m = 9223372036854775807\n"
            "    out m + 1\n"
            "    out m * 2\n"
            "}\n")
        self.assertEqual(out, "-9223372036854775808\n-2\n")

    def test_logic_nodes(self):
        rc, out = run_src(
            "#bin/\nfn main() {\n"
            "    out 1 and 2\n"
            "    out 0 and 2\n"
            "    out 0 or 0\n"
            "    out 0 or 5\n"
            "    out not 0\n"
            "    out not 3\n"
            "}\n")
        self.assertEqual(out, "1\n0\n0\n1\n1\n0\n")

    def test_strings(self):
        rc, out = run_src(
            "#bin/\nfn main() {\n"
            '    out "ab" + "cd"\n'
            '    out "ab" == "ab"\n'
            '    out "ab" < "b"\n'
            '    out len("hello")\n'
            '    out str(42) + "!"\n'
            '    out num("17") + 3\n'
            "}\n")
        self.assertEqual(out, "abcd\n1\n1\n5\n42!\n20\n")

    def test_if_else_chain(self):
        rc, out = run_src(
            "#bin/\nfn main() {\n"
            "    let x = 7\n"
            "    if x < 5 { out \"low\" } else if x < 10 { out \"mid\" } else { out \"high\" }\n"
            "}\n")
        self.assertEqual(out, "mid\n")

    def test_while_loop(self):
        rc, out = run_src(
            "#bin/\nfn main() {\n"
            "    let i = 0\n"
            "    let s = 0\n"
            "    while i <= 100 {\n"
            "        set s = s + i\n"
            "        set i = i + 1\n"
            "    }\n"
            "    out s\n"
            "}\n")
        self.assertEqual(out, "5050\n")

    def test_recursion(self):
        rc, out = run_src(
            "#bin/\nfn fib(n) {\n"
            "    if n < 2 { return n }\n"
            "    return fib(n - 1) + fib(n - 2)\n"
            "}\n"
            "fn main() { out fib(15) }\n")
        self.assertEqual(out, "610\n")

    def test_parallel_calls_deterministic(self):
        src = ("#bin/ threads=4\n"
               "fn slow(x) { return x * x }\n"
               "fn main() {\n"
               "    let a = slow(3)\n"
               "    let b = slow(4)\n"
               "    let c = slow(5)\n"
               "    out a + b + c\n"
               "}\n")
        for _ in range(5):
            rc, out = run_src(src)
            self.assertEqual(out, "50\n")

    def test_effect_order_stable_in_waves(self):
        src = ("#bin/ threads=4\n"
               "fn main() {\n"
               "    out 1 * 100\n"
               "    out 2 * 100\n"
               "    out 3 * 100\n"
               "    out 4 * 100\n"
               "}\n")
        for _ in range(5):
            rc, out = run_src(src)
            self.assertEqual(out, "100\n200\n300\n400\n")

    def test_div_by_zero_fault(self):
        rc, out = run_src("#bin/\nfn main() { let x = 1 / 0 }\n")
        self.assertEqual(rc, 1)

    def test_type_fault(self):
        rc, out = run_src('#bin/\nfn main() { let x = 1 + "a" }\n')
        self.assertEqual(rc, 1)

    def test_num_parse_fault(self):
        rc, out = run_src('#bin/\nfn main() { out num("zz") }\n')
        self.assertEqual(rc, 1)

    def test_binary_roundtrip(self):
        src = ("#bin/\nfn add(a, b) { return a + b }\n"
               "fn main() {\n"
               '    out add(20, 22)\n'
               '    out "sum done"\n'
               "}\n")
        prog = compile_source(src, "t.eil")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.ein")
            binfmt.save(path, prog)
            rc, out = run_file(path)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "42\nsum done\n")

    def test_binary_bad_magic(self):
        from eiltn.errors import LoadErr
        with self.assertRaises(LoadErr):
            binfmt.parse(b"NOPE" + b"\x00" * 32)

    def test_binary_truncated(self):
        from eiltn.errors import LoadErr
        prog = compile_source('#bin/\nfn main() { out 1 }\n', "t")
        data = binfmt.dump(prog)
        with self.assertRaises(LoadErr):
            binfmt.parse(data[:len(data) // 2])

    def test_parallel_wave_threaded_matches_sequential(self):
        src = ("#bin/\n"
               "fn work(n) {\n"
               "    let i = 0\n"
               "    let a = 0\n"
               "    while i < n { set a = a + i\n set i = i + 1 }\n"
               "    return a\n"
               "}\n"
               "fn main() {\n"
               "    let x = work(64)\n"
               "    let y = work(64)\n"
               "    out x + y\n"
               "}\n")
        _, single = run_src(src, threads=1)
        _, many = run_src(src, threads=8)
        self.assertEqual(single, many)
        self.assertEqual(single, "4032\n")


if __name__ == "__main__":
    unittest.main()
