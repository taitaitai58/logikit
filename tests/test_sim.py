"""Tests for the netlist extractor + fixpoint simulator (logikit.sim)."""
import tempfile
import unittest

from examples.circuits import and3_nand, mux2_nand, ring_osc_nand
from logikit.circ import emit
from logikit.sim import _EVAL, netlist_from_circ, simulate, truth_table
from tests import quiet


class GateEvalTest(unittest.TestCase):
    def test_basic_gates(self):
        self.assertEqual(_EVAL['NAND']([1, 1]), 0)
        self.assertEqual(_EVAL['NAND']([1, 0]), 1)
        self.assertEqual(_EVAL['AND']([1, 1]), 1)
        self.assertEqual(_EVAL['OR']([0, 0]), 0)
        self.assertEqual(_EVAL['NOR']([0, 0]), 1)
        self.assertEqual(_EVAL['NOT']([0]), 1)

    def test_xor_default_vs_odd_parity_differ_for_three_inputs(self):
        # Logisim's default XOR is "exactly one high"; _ODD is true parity.
        self.assertEqual(_EVAL['XOR']([1, 1, 1]), 0)        # not "exactly one"
        self.assertEqual(_EVAL['XOR_ODD']([1, 1, 1]), 1)    # odd parity
        self.assertEqual(_EVAL['XNOR']([1, 1, 1]), 1)
        self.assertEqual(_EVAL['XNOR_ODD']([1, 1, 1]), 0)


class TruthTableTest(unittest.TestCase):
    def _rows(self, name, builder):
        with tempfile.TemporaryDirectory() as d:
            emit(name, builder, d)
            with quiet():
                return truth_table(name, d)

    def test_mux2(self):
        # Y = (A and not S) or (B and S)
        rows = self._rows('mux2_nand', mux2_nand)
        got = {(r[0]['A'], r[0]['B'], r[0]['S']): r[1]['Y'] for r in rows}
        for (a, b, s), y in got.items():
            self.assertEqual(y, (a and not s) or (b and s), (a, b, s))
        self.assertTrue(all(stable for _, _, stable in rows))

    def test_and3(self):
        rows = self._rows('and3_nand', and3_nand)
        for ins, outs, stable in rows:
            expect = 1 if (ins['A'] and ins['B'] and ins['C']) else 0
            self.assertEqual(outs['Y'], expect, ins)

    def test_ring_oscillator_is_unstable(self):
        rows = self._rows('ring_osc_nand', ring_osc_nand)
        self.assertEqual(len(rows), 1)               # no inputs -> one row
        self.assertFalse(rows[0][2])                 # never settles


class FeedbackTest(unittest.TestCase):
    # NAND SR latch built directly as a netlist (nets are opaque tokens):
    #   Q = NAND(nS, Qb) ;  Qb = NAND(nR, Q)
    GATES = [('NAND', ['nS', 'Qb'], 'Q'),
             ('NAND', ['nR', 'Q'], 'Qb')]

    def test_hold_state_is_seed_dependent(self):
        for s in (0, 1):
            stable, v = simulate(self.GATES, {'nS': 1, 'nR': 1},
                                 seed={'Q': s, 'Qb': 1 - s})
            self.assertTrue(stable)
            self.assertEqual(v['Q'], s)
            self.assertEqual(v['Qb'], 1 - s)

    def test_set_and_reset(self):
        _, v = simulate(self.GATES, {'nS': 0, 'nR': 1})   # set -> Q=1
        self.assertEqual(v['Q'], 1)
        _, v = simulate(self.GATES, {'nS': 1, 'nR': 0})   # reset -> Q=0
        self.assertEqual(v['Q'], 0)


class NetlistTest(unittest.TestCase):
    def test_inputs_and_outputs_recovered(self):
        with tempfile.TemporaryDirectory() as d:
            emit('mux2_nand', mux2_nand, d)
            gates, inputs, outputs = netlist_from_circ('mux2_nand', d)
            self.assertEqual(sorted(inputs), ['A', 'B', 'S'])
            self.assertEqual(sorted(outputs), ['Y'])
            self.assertTrue(gates)


if __name__ == '__main__':
    unittest.main()
