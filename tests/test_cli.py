"""Tests for the unified command-line entry point (logikit.cli)."""
import tempfile
import unittest

from examples.circuits import mux2_nand
from logikit.circ import emit
from logikit.cli import main
from tests import quiet


class CliTest(unittest.TestCase):
    def setUp(self):
        self.d = tempfile.TemporaryDirectory()
        self.addCleanup(self.d.cleanup)
        emit('mux2_nand', mux2_nand, self.d.name)

    def test_check_ok(self):
        with quiet():
            self.assertEqual(main(['check', '--dir', self.d.name, 'mux2_nand']), 0)

    def test_check_fail_on_missing_file(self):
        with quiet():
            with self.assertRaises(FileNotFoundError):
                main(['check', '--dir', self.d.name, 'does_not_exist'])

    def test_sim_text(self):
        with quiet() as out:
            self.assertEqual(main(['sim', '--dir', self.d.name, 'mux2_nand']), 0)
        self.assertIn('A B S  |  Y', out.getvalue())

    def test_sim_markdown(self):
        with quiet() as out:
            self.assertEqual(
                main(['sim', '--dir', self.d.name, '--format', 'md', 'mux2_nand']), 0)
        self.assertIn('| A | B | S | Y |', out.getvalue())

    def test_doctor_returns_int(self):
        with quiet():
            rc = main(['doctor'])
        self.assertIn(rc, (0, 1))

    def test_no_command_prints_help(self):
        with quiet() as out:
            self.assertEqual(main([]), 0)
        self.assertIn('usage', out.getvalue().lower())

    def test_examples_subcommand_generates(self):
        # `examples` writes into build/ (cwd); just confirm it returns cleanly.
        with quiet():
            rc = main(['examples', '--no-check'])
        self.assertEqual(rc, 0)


if __name__ == '__main__':
    unittest.main()
