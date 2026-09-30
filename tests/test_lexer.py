import unittest

from eiltn.lexer import tokenize
from eiltn.errors import SyntaxErr


class TestLexer(unittest.TestCase):
    def test_header_directive(self):
        toks = tokenize("#bin/\n", "t")
        kinds = [t.kind for t in toks]
        self.assertEqual(kinds[0], "dir")
        self.assertEqual(toks[0].value, "#bin/")

    def test_header_required_before_anything(self):
        from eiltn.parser import parse
        with self.assertRaises(SyntaxErr):
            parse(tokenize("fn main() {}\n", "t"), "t")

    def test_comment_rejected(self):
        with self.assertRaises(SyntaxErr):
            tokenize("#bin/\nfn main() {}\n# hello\n", "t")

    def test_late_hash_rejected(self):
        with self.assertRaises(SyntaxErr):
            tokenize("#bin/\n# note\n", "t")

    def test_emoji_rejected(self):
        with self.assertRaises(SyntaxErr):
            tokenize("#bin/\nfn main() { out \"hi \U0001F600\" }\n", "t")

    def test_numbers(self):
        toks = tokenize("#bin/\n1 0x1F 0b1010 1_000 0xFFFFFFFFFFFFFFFF\n", "t")
        vals = [t.value for t in toks if t.kind == "int"]
        self.assertEqual(vals, [1, 31, 10, 1000, -1])

    def test_literal_overflow_rejected(self):
        with self.assertRaises(SyntaxErr):
            tokenize("#bin/\n18446744073709551616\n", "t")

    def test_strings_with_escapes(self):
        src = '#bin/\n' + '"a\\nb\\t\\"q\\\\s\\"\\x41"\n'
        toks = tokenize(src, "t")
        s = [t.value for t in toks if t.kind == "str"][0]
        self.assertEqual(s, 'a\nb\t"q\\s"A')

    def test_unterminated_string(self):
        with self.assertRaises(SyntaxErr):
            tokenize('#bin/\n"oops\n', "t")

    def test_two_char_ops(self):
        toks = tokenize("#bin/\n<< >> == != <= >=\n", "t")
        ops = [t.value for t in toks if t.kind == "op"]
        self.assertEqual(ops, ["<<", ">>", "==", "!=", "<=", ">="])

    def test_bang_alone_rejected(self):
        with self.assertRaises(SyntaxErr):
            tokenize("#bin/\nif !x {}\n", "t")

    def test_newlines_collapse(self):
        toks = tokenize("#bin/\n\n\n\n", "t")
        self.assertEqual([t.kind for t in toks], ["dir", "nl", "eof"])


if __name__ == "__main__":
    unittest.main()
