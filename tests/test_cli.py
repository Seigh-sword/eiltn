import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestCli(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, "-m", "eiltn"] + list(args),
            cwd=ROOT, capture_output=True, text=True, timeout=120)

    def test_run_example(self):
        p = self.run_cli("run", "examples/fib.eil")
        self.assertEqual(p.returncode, 0)
        self.assertEqual(p.stdout.strip(), "46368")

    def test_build_and_run_binary(self):
        with tempfile.TemporaryDirectory() as d:
            ein_path = os.path.join(d, "fib.ein")
            p1 = self.run_cli("build", "examples/fib.eil", "-o", ein_path)
            self.assertEqual(p1.returncode, 0, p1.stderr)
            self.assertIn("ein nodes", p1.stdout)
            p2 = self.run_cli("run", ein_path)
            self.assertEqual(p2.returncode, 0, p2.stderr)
            self.assertEqual(p2.stdout.strip(), "46368")

    def test_dis_shows_nodes(self):
        p = self.run_cli("dis", "examples/fib.eil")
        self.assertEqual(p.returncode, 0)
        self.assertIn("CONST", p.stdout)
        self.assertIn("STORE", p.stdout)
        self.assertIn("BR", p.stdout)
        self.assertIn("RET", p.stdout)

    def test_stats_flag(self):
        p = self.run_cli("run", "-s", "examples/fib.eil")
        self.assertEqual(p.returncode, 0)
        self.assertIn("waves", p.stderr)

    def test_missing_file_is_clean_error(self):
        p = self.run_cli("run", "nope.eil")
        self.assertEqual(p.returncode, 1)
        self.assertTrue(p.stderr.startswith("error:"))

    def test_version(self):
        p = self.run_cli("--version")
        self.assertEqual(p.returncode, 0)
        self.assertIn("eiltn", p.stdout)


if __name__ == "__main__":
    unittest.main()
