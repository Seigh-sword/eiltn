#!/usr/bin/python3

import io
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from eiltn.api import compile_source
from eiltn import binfmt
from eiltn.dispatcher import run_program


def run_src(src, threads=0, args=None, name="t.eil"):
    prog = compile_source(src, name)
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        rc, _ = run_program(prog, threads=threads, args=args)
    return rc, out.getvalue(), err.getvalue()


def run_file(path, threads=0, args=None):
    prog = binfmt.load(path)
    out = io.StringIO()
    with redirect_stdout(out):
        rc, _ = run_program(prog, threads=threads, args=args)
    return rc, out.getvalue()


class TestWords(unittest.TestCase):
    def test_hello(self):
        rc, out, _ = run_src('fn main() { println("hello")\n println("world") }\n')
        self.assertEqual(rc, 0)
        self.assertEqual(out, "hello\nworld\n")

    def test_arithmetic(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(7 / 2)\n"
            "    println((0 - 7) / 2)\n"
            "    println((0 - 7) % 2)\n"
            "    println(1 << 63)\n"
            "    println(~0)\n"
            "}\n")
        self.assertEqual(out, "3\n-3\n-1\n-9223372036854775808\n-1\n")

    def test_wraparound(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    let m = 9223372036854775807\n"
            "    println(m + 1)\n"
            "    println(m * 2)\n"
            "}\n")
        self.assertEqual(out, "-9223372036854775808\n-2\n")

    def test_logic(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(1 and 2)\n"
            "    println(0 and 2)\n"
            "    println(0 or 0)\n"
            "    println(0 or 5)\n"
            "    println(not 0)\n"
            "    println(not 3)\n"
            "}\n")
        self.assertEqual(out, "1\n0\n0\n1\n1\n0\n")

    def test_int_compare(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(3 < 4)\n"
            "    println(4 <= 4)\n"
            "    println(5 > 6)\n"
            "    println(6 >= 7)\n"
            "    println(1 == 1)\n"
            "    println(1 != 1)\n"
            "}\n")
        self.assertEqual(out, "1\n1\n0\n0\n1\n0\n")


class TestFloats(unittest.TestCase):
    def test_float_math(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(3.5 + 1.5)\n"
            "    println(3.0 * 2.0)\n"
            "    println(7.0 / 2.0)\n"
            "    println(1.5 - 0.5)\n"
            "}\n")
        self.assertEqual(out, "5.0\n6.0\n3.5\n1.0\n")

    def test_mixed_promotes(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(3 + 0.5)\n"
            "    println(0.5 + 3)\n"
            "    println(7 / 2.0)\n"
            "}\n")
        self.assertEqual(out, "3.5\n3.5\n3.5\n")

    def test_int_div_stays_int(self):
        rc, out, _ = run_src("fn main() { println(7 / 2)\n println(7 % 2) }\n")
        self.assertEqual(out, "3\n1\n")

    def test_float_compare(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(2.5 > 2.0)\n"
            "    println(2.5 == 2.5)\n"
            "    println(1.0 < 1.5)\n"
            "}\n")
        self.assertEqual(out, "1\n1\n1\n")

    def test_min_max_floats(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(min(2.5, 2.0))\n"
            "    println(max(1, 2.5))\n"
            "}\n")
        self.assertEqual(out, "2.0\n2.5\n")

    def test_math_builtins(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(sqrt(4.0))\n"
            "    println(pow(2.0, 10.0))\n"
            "    println(floor(3.99))\n"
            "    println(ceil(0.1))\n"
            "    println(round(3.5))\n"
            "    println(abs(0 - 7))\n"
            "    println(abs(-2.5))\n"
            "}\n")
        self.assertEqual(out, "2.0\n1024.0\n3\n1\n4\n7\n2.5\n")

    def test_conversions(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    println(int(3.99))\n"
            "    println(float(7))\n"
            "    println(num(\"2.5\") + 1.5)\n"
            "    println(num(\"42\") + 1)\n"
            "    println(str(1.5) + \"!\")\n"
            "}\n")
        self.assertEqual(out, "3\n7.0\n4.0\n43\n1.5!\n")


class TestStrings(unittest.TestCase):
    def test_concat_and_compare(self):
        rc, out, _ = run_src(
            'fn main() {\n'
            '    println("ab" + "cd")\n'
            '    println("ab" == "ab")\n'
            '    println("ab" < "b")\n'
            '}\n')
        self.assertEqual(out, "abcd\n1\n1\n")

    def test_string_builtins(self):
        rc, out, _ = run_src(
            'fn main() {\n'
            '    println(len("hello"))\n'
            '    println(upper("abc"))\n'
            '    println(lower("ABC"))\n'
            '    println(substr("eiltn", 1, 3))\n'
            '    println(contains("eiltn", "il"))\n'
            '    println(index("eiltn", "t"))\n'
            '    println(index("eiltn", "zz"))\n'
            '    println(replace("aa", "a", "b"))\n'
            '    println(reverse("abc"))\n'
            '    println(repeat("ab", 3))\n'
            '    println(trim("  hi  ") + "!")\n'
            '    println(chr(69) + chr(73))\n'
            '    println(ord("A"))\n'
            '}\n')
        self.assertEqual(out, "5\nABC\nabc\nil\n1\n3\n-1\nbb\ncba\nababab\nhi!\nEI\n65\n")

    def test_printf_formats(self):
        rc, out, eout = run_src(
            'fn main() {\n'
            '    out.printf("%d %s %.2f %x %c %%\\n", 42, "ok", 3.14159, 255, 33)\n'
            '    err.printf("e%d\\n", 7)\n'
            '}\n')
        self.assertEqual(out, "42 ok 3.14 ff ! %\n")
        self.assertEqual(eout, "e7\n")

    def test_printf_bad_format_faults(self):
        rc, out, _ = run_src('fn main() { out.printf("%d\\n", "nope") }\n')
        self.assertEqual(rc, 1)


class TestControl(unittest.TestCase):
    def test_if_else_chain(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    let x = 7\n"
            '    if x < 5 { println("low") } else if x < 10 { println("mid") } else { println("high") }\n'
            "}\n")
        self.assertEqual(out, "mid\n")

    def test_while(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    let i = 0\n"
            "    let s = 0\n"
            "    while i <= 100 {\n"
            "        set s = s + i\n"
            "        set i = i + 1\n"
            "    }\n"
            "    println(s)\n"
            "}\n")
        self.assertEqual(out, "5050\n")

    def test_for(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    let s = 0\n"
            "    for let i = 1; i <= 100; i = i + 1 {\n"
            "        set s = s + i\n"
            "    }\n"
            "    println(s)\n"
            "}\n")
        self.assertEqual(out, "5050\n")

    def test_for_bare_assign(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    let i = 0\n"
            "    for i = 0; i < 3; i = i + 1 { println(i) }\n"
            "}\n")
        self.assertEqual(out, "0\n1\n2\n")

    def test_break(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    let j = 0\n"
            "    while true {\n"
            "        set j = j + 1\n"
            "        if j >= 3 { break }\n"
            "    }\n"
            "    println(j)\n"
            "}\n")
        self.assertEqual(out, "3\n")

    def test_break_in_for(self):
        rc, out, _ = run_src(
            "fn main() {\n"
            "    for let i = 0; i < 100; i = i + 1 {\n"
            "        if i == 2 { break }\n"
            "        println(i)\n"
            "    }\n"
            "}\n")
        self.assertEqual(out, "0\n1\n")

    def test_recursion(self):
        rc, out, _ = run_src(
            "fn fib(n) {\n"
            "    if n < 2 { return n }\n"
            "    return fib(n - 1) + fib(n - 2)\n"
            "}\n"
            "fn main() { println(fib(15)) }\n")
        self.assertEqual(out, "610\n")

    def test_parallel_calls_deterministic(self):
        src = ("fn slow(x) { return x * x }\n"
               "fn main() {\n"
               "    let a = slow(3)\n"
               "    let b = slow(4)\n"
               "    let c = slow(5)\n"
               "    println(a + b + c)\n"
               "}\n")
        for _ in range(5):
            rc, out, _ = run_src(src, threads=4)
            self.assertEqual(out, "50\n")

    def test_threaded_matches_sequential(self):
        src = ("fn work(n) {\n"
               "    let i = 0\n"
               "    let a = 0\n"
               "    while i < n { set a = a + i\n set i = i + 1 }\n"
               "    return a\n"
               "}\n"
               "fn main() {\n"
               "    let x = work(64)\n"
               "    let y = work(64)\n"
               "    println(x + y)\n"
               "}\n")
        _, single, _ = run_src(src, threads=1)
        _, many, _ = run_src(src, threads=8)
        self.assertEqual(single, many)
        self.assertEqual(single, "4032\n")


class TestFaults(unittest.TestCase):
    def test_div_by_zero(self):
        rc, out, _ = run_src("fn main() { let x = 1 / 0 }\n")
        self.assertEqual(rc, 1)

    def test_mod_by_zero(self):
        rc, out, _ = run_src("fn main() { let x = 1 % 0 }\n")
        self.assertEqual(rc, 1)

    def test_type_fault(self):
        rc, out, _ = run_src('fn main() { let x = 1 + "a" }\n')
        self.assertEqual(rc, 1)

    def test_ordering_mixed_fault(self):
        rc, out, _ = run_src('fn main() { let x = 1 < "a" }\n')
        self.assertEqual(rc, 1)

    def test_sqrt_negative_is_nan(self):
        rc, out, _ = run_src("fn main() { println(sqrt(0 - 1.0)) }\n")
        self.assertEqual(out.strip(), "nan")

    def test_exit_code(self):
        rc, out, _ = run_src("fn main() { println(1)\n exit(3) }\n")
        self.assertEqual(rc, 3)

    def test_argv(self):
        rc, out, _ = run_src('fn main() { println(argc())\n println(argv(0)) }',
                             args=["one", "two"])
        self.assertEqual(out, "2\none\n")

    def test_rand_range(self):
        rc, out, _ = run_src("fn main() { println(rand() >= 0.0 and rand() < 1.0) }\n")
        self.assertEqual(out, "1\n")


class TestBinary(unittest.TestCase):
    def test_roundtrip(self):
        src = ('fn add(a, b) { return a + b }\n'
               'fn main() {\n'
               '    println(add(20, 22))\n'
               '    out.printf("%s %.1f\\n", "sum done", 5.0)\n'
               "}\n")
        prog = compile_source(src, "t.eil")
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.ein")
            binfmt.save(path, prog)
            rc, out = run_file(path)
        self.assertEqual(rc, 0)
        self.assertEqual(out, "42\nsum done 5.0\n")

    def test_bad_magic(self):
        from eiltn.errors import LoadErr
        with self.assertRaises(LoadErr):
            binfmt.parse(b"NOPE" + b"\x00" * 32)

    def test_truncated(self):
        from eiltn.errors import LoadErr
        prog = compile_source("fn main() { println(1) }\n", "t")
        data = binfmt.dump(prog)
        with self.assertRaises(LoadErr):
            binfmt.parse(data[:len(data) // 2])

    def test_float_consts_survive(self):
        prog = compile_source("fn main() { println(2.5) }\n", "t")
        prog2 = binfmt.parse(binfmt.dump(prog), "t")
        self.assertIn(2.5, prog2.consts)


if __name__ == "__main__":
    unittest.main()
