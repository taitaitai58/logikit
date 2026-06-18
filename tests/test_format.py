"""Tests for truth-table export to Markdown / LaTeX (logikit.sim.format_table)."""
import tempfile
import unittest

from examples.circuits import mux2_nand, ring_osc_nand
from logikit.circ import emit
from logikit.sim import format_table, truth_table, truth_table_str
from tests import quiet


# A tiny hand-built result set: 1 input A, 1 output Y = NOT A.
ROWS_NOT = ([("A")], ["Y"],
            [({'A': 0}, {'Y': 1}, True), ({'A': 1}, {'Y': 0}, True)])


class FormatTest(unittest.TestCase):
    def test_markdown_shape(self):
        in_names, out_names, rows = ROWS_NOT
        md = format_table(in_names, out_names, rows, 'md')
        lines = md.splitlines()
        self.assertEqual(lines[0], "| A | Y |")
        self.assertEqual(lines[1], "| --- | --- |")
        self.assertEqual(lines[2], "| 0 | 1 |")
        self.assertEqual(lines[3], "| 1 | 0 |")

    def test_latex_shape(self):
        in_names, out_names, rows = ROWS_NOT
        tex = format_table(in_names, out_names, rows, 'latex')
        self.assertIn(r"\begin{tabular}{c|c}", tex)
        self.assertIn(r"A & Y \\", tex)
        self.assertIn(r"\hline", tex)
        self.assertIn(r"0 & 1 \\", tex)
        self.assertIn(r"\end{tabular}", tex)

    def test_unstable_row_marked(self):
        rows = [({}, {'Q': 0}, False)]
        md = format_table([], ['Q'], rows, 'md')
        self.assertIn("—", md)
        self.assertIn("oscillates", md)
        tex = format_table([], ['Q'], rows, 'latex')
        self.assertIn(r"\textemdash{}", tex)

    def test_unknown_format_rejected(self):
        with self.assertRaises(ValueError):
            format_table(['A'], ['Y'], [], 'csv')


class TruthTableStrTest(unittest.TestCase):
    def test_mux2_markdown_has_a_row_per_combo(self):
        with tempfile.TemporaryDirectory() as d:
            emit('mux2_nand', mux2_nand, d)
            md = truth_table_str('mux2_nand', d, 'md')
        self.assertIn("| A | B | S | Y |", md)
        # 2 header rows + 2**3 data rows
        self.assertEqual(len([ln for ln in md.splitlines() if ln.startswith('|')]),
                         2 + 8)

    def test_ring_oscillator_marked_unstable(self):
        with tempfile.TemporaryDirectory() as d:
            emit('ring_osc_nand', ring_osc_nand, d)
            md = truth_table_str('ring_osc_nand', d, 'md')
        self.assertIn("oscillates", md)


class TextOutputUnchangedTest(unittest.TestCase):
    """The refactor must not change the plain-text truth_table output/return."""

    def test_text_table_still_prints_and_returns_rows(self):
        with tempfile.TemporaryDirectory() as d:
            emit('mux2_nand', mux2_nand, d)
            with quiet() as out:
                rows = truth_table('mux2_nand', d)
        text = out.getvalue()
        self.assertIn("inputs ['A', 'B', 'S']  ->  outputs ['Y']", text)
        self.assertIn("A B S  |  Y", text)
        self.assertEqual(len(rows), 8)
        self.assertEqual(rows[0], ({'A': 0, 'B': 0, 'S': 0}, {'Y': 0}, True))


if __name__ == '__main__':
    unittest.main()
