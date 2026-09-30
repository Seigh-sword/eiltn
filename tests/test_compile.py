import unittest

from eiltn.api import compile_source
from eiltn.errors import SyntaxErr, BuildErr
from eiltn import ein


HELLO = "#bin/\nfn main() {\n    out \"hi\"\n}\n"


class TestBuild(unittest.TestCase):
    def test_hello_builds_nodes(self):
        prog = compile_source(HELLO, "t")
        self.assertEqual(len(prog.funcs), 1)
        main = prog.funcs[0]
        ops = [x.op for x in main.blocks[0].ins]
        self.assertIn(ein.OUT, ops)
        self.assertEqual(ops[-1], ein.RET)
        kinds = [x.ops[0][0] for x in main.blocks[0].ins if x.op == ein.OUT]
        self.assertEqual(kinds, [ein.K_CONST])

    def test_missing_header(self):
        with self.assertRaises(SyntaxErr):
            compile_source("fn main() {}\n", "t")

    def test_no_main(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn helper() { return 1 }\n", "t")

    def test_main_with_params_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn main(x) { out x }\n", "t")

    def test_double_let_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn main() { let a = 1\n let a = 2 }\n", "t")

    def test_set_before_let_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn main() { set a = 1 }\n", "t")

    def test_use_before_let_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn main() { out a\n let a = 1 }\n", "t")

    def test_unknown_fn_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn main() { let x = mystery(1) }\n", "t")

    def test_arity_mismatch_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn f(a) { return a }\nfn main() { f(1, 2) }\n", "t")

    def test_unreachable_rejected(self):
        with self.assertRaises(BuildErr):
            compile_source("#bin/\nfn main() { return 1\n out 2 }\n", "t")

    def test_unknown_header_attr_rejected(self):
        with self.assertRaises(SyntaxErr):
            compile_source("#bin/ color=3\nfn main() {}\n", "t")

    def test_threads_attr_parsed(self):
        prog = compile_source("#bin/ threads=4\nfn main() {}\n", "t")
        self.assertEqual(prog.threads, 4)

    def test_call_graph_and_if_blocks(self):
        src = ("#bin/\n"
               "fn f(x) { if x < 2 { return x } return f(x - 1) + f(x - 2) }\n"
               "fn main() { out f(6) }\n")
        prog = compile_source(src, "t")
        f = prog.funcs[0]
        self.assertGreaterEqual(len(f.blocks), 3)
        call_count = sum(1 for b in f.blocks for x in b.ins if x.op == ein.CALL)
        self.assertEqual(call_count, 2)


if __name__ == "__main__":
    unittest.main()
