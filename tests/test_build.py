#!/usr/bin/python3

import unittest

from eiltn.api import compile_source
from eiltn.errors import SyntaxErr, BuildErr
from eiltn import ein


class TestBuild(unittest.TestCase):
    def test_hello_builds_out_node(self):
        prog = compile_source('fn main() {\n    println("hi")\n}\n', "t")
        main = prog.funcs[0]
        ops = [x.op for x in main.blocks[0].ins]
        self.assertIn(ein.OUT, ops)
        self.assertEqual(ops[-1], ein.RET)
        outs = [x for x in main.blocks[0].ins if x.op == ein.OUT]
        self.assertEqual(outs[0].ops[0][0], ein.K_CONST)

    def test_no_main_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn helper() { return 1 }\n", "t")

    def test_main_with_params_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main(x) { println(x) }\n", "t")

    def test_empty_program_rejected(self):
        with self.assertRaises(SyntaxErr):
            compile_source("$ nothing here\n", "t")

    def test_double_let_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { let a = 1\n let a = 2 }\n", "t")

    def test_set_before_let_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { set a = 1 }\n", "t")

    def test_use_before_let_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { println(a)\n let a = 1 }\n", "t")

    def test_unknown_fn_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source('fn main() { let x = mystery(1) }\n', "t")

    def test_arity_mismatch_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn f(a) { return a }\nfn main() { f(1, 2) }\n", "t")

    def test_unreachable_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { return 1\n println(2) }\n", "t")

    def test_break_outside_loop_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { break }\n", "t")

    def test_io_members(self):
        prog = compile_source(
            'fn main() {\n'
            '    out.println(1)\n'
            '    err.println(2)\n'
            '    out.printf("%d\\n", 3)\n'
            '    err.printf("%d\\n", 4)\n'
            '}\n', "t")
        ops = [x.op for x in prog.funcs[0].blocks[0].ins]
        self.assertEqual(ops.count(ein.OUT), 1)
        self.assertEqual(ops.count(ein.ERR), 1)
        self.assertEqual(ops.count(ein.PRINTF), 2)

    def test_unknown_io_member_rejected(self):
        with self.assertRaises(SyntaxErr):
            compile_source('fn main() { out.shout("x") }\n', "t")

    def test_dotted_on_plain_ident_rejected(self):
        with self.assertRaises(SyntaxErr):
            compile_source('fn main() { let x = foo.bar() }\n', "t")

    def test_printf_needs_format(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { out.printf() }\n", "t")

    def test_min_max_desugar_to_select(self):
        prog = compile_source("fn main() { println(min(1, 2))\n println(max(1, 2)) }\n", "t")
        ops = [x.op for x in prog.funcs[0].blocks[0].ins]
        self.assertIn(ein.SELECT, ops)
        self.assertEqual(ops.count(ein.SELECT), 2)
        self.assertNotIn(ein.NATIVE, ops)

    def test_native_trap_lowers(self):
        prog = compile_source("fn main() { println(sqrt(2.0)) }\n", "t")
        ops = [x.op for x in prog.funcs[0].blocks[0].ins]
        self.assertIn(ein.NATIVE, ops)

    def test_native_arity_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { println(sqrt()) }\n", "t")

    def test_unknown_builtin_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("fn main() { println(frobnicate(1)) }\n", "t")

    def test_for_lowering_blocks(self):
        prog = compile_source(
            "fn main() {\n"
            "    let s = 0\n"
            "    for let i = 0; i < 5; i = i + 1 {\n"
            "        set s = s + i\n"
            "    }\n"
            "}\n", "t")
        f = prog.funcs[0]
        self.assertGreaterEqual(len(f.blocks), 4)
        terms = [b.ins[-1].op for b in f.blocks]
        self.assertIn(ein.BR, terms)

    def test_float_const_pool(self):
        prog = compile_source("fn main() { let x = 2.5\n println(x) }\n", "t")
        self.assertIn(2.5, prog.consts)

    def test_call_graph(self):
        src = ("fn f(x) { if x < 2 { return x } return f(x - 1) + f(x - 2) }\n"
               "fn main() { println(f(6)) }\n")
        prog = compile_source(src, "t")
        f = prog.funcs[0]
        self.assertGreaterEqual(len(f.blocks), 3)
        call_count = sum(1 for b in f.blocks for x in b.ins if x.op == ein.CALL)
        self.assertEqual(call_count, 2)


if __name__ == "__main__":
    unittest.main()
