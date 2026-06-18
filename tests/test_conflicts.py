"""Tests for bus-conflict (multi-driver) detection (logikit.sim.find_conflicts)."""
import tempfile
import unittest

from examples.circuits import mux2_nand, ring_osc_nand
from logikit.circ import emit
from logikit.sim import find_conflicts, netlist_from_circ, simulate
from tests import quiet


class FindConflictsTest(unittest.TestCase):
    def test_clean_netlist_has_no_conflict(self):
        gates = [('AND', ['a', 'b'], 'x'), ('NOT', ['x'], 'y')]
        self.assertEqual(find_conflicts(gates, {'a': 'a', 'b': 'b'}), [])

    def test_two_gate_outputs_on_one_net(self):
        gates = [('OR', ['a', 'b'], 'X'), ('AND', ['a', 'b'], 'X')]
        conflicts = find_conflicts(gates, {})
        self.assertEqual(len(conflicts), 1)
        net, who = conflicts[0]
        self.assertEqual(net, 'X')
        self.assertEqual(len(who), 2)

    def test_input_pin_tied_onto_a_gate_output(self):
        gates = [('NOT', ['a'], 'Y')]
        # input pin 'B' shorted onto the gate's output net 'Y'
        conflicts = find_conflicts(gates, {'a': 'a', 'B': 'Y'})
        self.assertEqual([n for n, _ in conflicts], ['Y'])


class StrictSimulateTest(unittest.TestCase):
    def test_strict_raises_on_multi_driver(self):
        gates = [('OR', ['a', 'b'], 'X'), ('AND', ['a', 'b'], 'X')]
        with self.assertRaises(ValueError):
            simulate(gates, {'a': 1, 'b': 0}, strict=True)

    def test_non_strict_still_returns_an_order_dependent_value(self):
        gates = [('OR', ['a', 'b'], 'X'), ('AND', ['a', 'b'], 'X')]
        stable, val = simulate(gates, {'a': 1, 'b': 0})   # no raise
        self.assertTrue(stable)
        self.assertIn('X', val)

    def test_strict_ok_on_clean_circuit(self):
        gates = [('AND', ['a', 'b'], 'x')]
        stable, _ = simulate(gates, {'a': 1, 'b': 1}, strict=True)
        self.assertTrue(stable)


class RealCircuitsAreCleanTest(unittest.TestCase):
    def test_examples_have_no_conflicts(self):
        for name, builder in (('mux2_nand', mux2_nand),
                              ('ring_osc_nand', ring_osc_nand)):
            with tempfile.TemporaryDirectory() as d:
                emit(name, builder, d)
                gates, inputs, _ = netlist_from_circ(name, d)
                self.assertEqual(find_conflicts(gates, inputs), [], name)

    def test_truth_table_warns_on_conflict_free_run_silently(self):
        # A clean circuit prints no [CONFLICT] line.
        with tempfile.TemporaryDirectory() as d:
            emit('mux2_nand', mux2_nand, d)
            from logikit.sim import truth_table
            with quiet() as out:
                truth_table('mux2_nand', d)
            self.assertNotIn('[CONFLICT]', out.getvalue())


if __name__ == '__main__':
    unittest.main()
