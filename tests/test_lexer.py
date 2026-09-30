#!/usr/bin/python3

import unittest

from eiltn.lexer import tokenize
from eiltn.errors import SyntaxErr


class TestComments(unittest.TestCase):
    def test_line_comment(self):
        toks = tokenize("$ hi there\nfn main() {}\n", "t")
        vals = [t.value for t in toks if t.kind in ("kw", "op")]
        self.assertEqual(vals, ["fn", "(", ")", "{", "}"])

    def test_comment_at_end_of_line(self):
        toks = tokenize("fn main() { $ trailing\n }\n", "t")
        self.assertNotIn("#", [t.value for t in toks])

    def test_block_comment(self):
        src = "-$\nhello\nmulti line\nok bye\n$-\nfn main() {}\n"
        toks = tokenize(src, "t")
        self.assertEqual([t.value for t in toks if t.kind == "kw"], ["fn"])

    def test_block_comment_single_line(self):
        toks = tokenize("-$ one line $- fn main() {}", "t")
        self.assertEqual([t.value for t in toks if t.kind == "kw"], ["fn"])

    def test_unterminated_block_comment(self):
        with self.assertRaises(SyntaxErr):
            tokenize("-$\nnever closed\n", "t")

    def test_comments_advance_lines(self):
        toks = tokenize("$ a\n-$ b\nc $-\nfn main() {}\n", "t")
        fn = [t for t in toks if t.kind == "kw"][0]
        self.assertEqual(fn.line, 4)

    def test_hash_is_not_a_comment(self):
        with self.assertRaises(SyntaxErr):
            tokenize("# not a comment\n", "t")

    def test_emoji_rejected(self):
        with self.assertRaises(SyntaxErr):
            tokenize('fn main() { println("hi \U0001F600") }\n', "t")

    def test_emoji_in_comment_ok(self):
        tokenize("$ a comment with \U0001F600 is fine\nfn main() {}\n", "t")


class TestLiterals(unittest.TestCase):
    def test_ints(self):
        toks = tokenize("1 0x1F 0b1010 1_000 0xFFFFFFFFFFFFFFFF\n", "t")
        vals = [t.value for t in toks if t.kind == "int"]
        self.assertEqual(vals, [1, 31, 10, 1000, -1])

    def test_floats(self):
        toks = tokenize("3.14 2.0 1e3 1.5e-2 0.5\n", "t")
        vals = [t.value for t in toks if t.kind == "float"]
        self.assertEqual(vals, [3.14, 2.0, 1000.0, 0.015, 0.5])

    def test_float_needs_digit_after_dot(self):
        with self.assertRaises(SyntaxErr):
            tokenize("1.\n", "t")

    def test_int_overflow(self):
        with self.assertRaises(SyntaxErr):
            tokenize("18446744073709551616\n", "t")

    def test_strings_with_escapes(self):
        src = '"a\\nb\\t\\"q\\\\s\\"\\x41"\n'
        toks = tokenize(src, "t")
        s = [t.value for t in toks if t.kind == "str"][0]
        self.assertEqual(s, 'a\nb\t"q\\s"A')

    def test_unterminated_string(self):
        with self.assertRaises(SyntaxErr):
            tokenize('"oops\n', "t")


class TestOps(unittest.TestCase):
    def test_two_char_ops(self):
        toks = tokenize("<< >> == != <= >=\n", "t")
        ops = [t.value for t in toks if t.kind == "op"]
        self.assertEqual(ops, ["<<", ">>", "==", "!=", "<=", ">="])

    def test_bang_alone_rejected(self):
        with self.assertRaises(SyntaxErr):
            tokenize("if !x {}\n", "t")

    def test_keywords(self):
        toks = tokenize("fn let set if else while for break return true false and or not\n", "t")
        kws = [t.value for t in toks if t.kind == "kw"]
        self.assertEqual(len(kws), 14)
        self.assertNotIn("out", kws)
        self.assertNotIn("err", kws)

    def test_newlines_collapse(self):
        toks = tokenize("\n\n\n\n", "t")
        self.assertEqual([t.kind for t in toks], ["eof"])


if __name__ == "__main__":
    unittest.main()
