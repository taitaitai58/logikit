"""Tests for the static connectivity check (logikit.check)."""
import tempfile
import unittest

from logikit.check import UF, build_nets, check, on_seg
from logikit.circ import emit
from tests import quiet


class PrimitiveTest(unittest.TestCase):
    def test_on_seg(self):
        self.assertTrue(on_seg((5, 0), (0, 0), (10, 0)))    # interior, horizontal
        self.assertTrue(on_seg((0, 5), (0, 0), (0, 10)))    # interior, vertical
        self.assertTrue(on_seg((0, 0), (0, 0), (10, 0)))    # endpoint
        self.assertFalse(on_seg((5, 1), (0, 0), (10, 0)))   # off the line
        self.assertFalse(on_seg((20, 0), (0, 0), (10, 0)))  # beyond the segment

    def test_union_find(self):
        uf = UF()
        uf.union('a', 'b')
        uf.union('b', 'c')
        self.assertEqual(uf.find('a'), uf.find('c'))
        self.assertNotEqual(uf.find('a'), uf.find('z'))

    def test_t_junction_connects_but_crossing_does_not(self):
        # T-junction: wire B's endpoint (5,0) lands on wire A's interior -> joined.
        uf = build_nets([((0, 0), (10, 0)), ((5, 0), (5, 10))], [])
        self.assertEqual(uf.find((0, 0)), uf.find((5, 10)))
        # Pure crossing: B passes through (5,0) but has no endpoint there, so the
        # two wires merely cross and are NOT connected.
        uf2 = build_nets([((0, 0), (10, 0)), ((5, -5), (5, 5))], [])
        self.assertNotEqual(uf2.find((5, -5)), uf2.find((0, 0)))


class CheckTest(unittest.TestCase):
    def _emit_and_check(self, name, builder):
        with tempfile.TemporaryDirectory() as d:
            emit(name, builder, d)
            with quiet() as out:
                ok = check(name, d)
            return ok, out.getvalue()

    def test_good_circuit_passes(self):
        def good(c):
            A = c.pin_in(0, 0, 'A')
            B = c.pin_in(0, 100, 'B')
            g = c.nand(200, 50)
            Yo = c.pin_out(320, 50, 'Y')
            c.fan(A, 80, [g['in'][0]], net='A')
            c.fan(B, 100, [g['in'][1]], net='B')
            c.path(g['out'], Yo)
            c.mark('Y', g['out'])

        ok, log = self._emit_and_check('good', good)
        self.assertTrue(ok, log)
        self.assertIn('OK', log)

    def test_short_is_detected(self):
        # Two input pins on different intended nets, wired straight together.
        def shorted(c):
            A = c.pin_in(0, 0, 'A')
            B = c.pin_in(0, 100, 'B')
            c.w(A, B)                       # vertical wire merges the two nets

        ok, log = self._emit_and_check('shorted', shorted)
        self.assertFalse(ok)
        self.assertIn('SHORT', log)

    def test_open_is_detected(self):
        # One net marked across two ports that are never wired together.
        def opened(c):
            A = c.pin_in(0, 0, 'A')
            g = c.nand(200, 0)
            c.mark('A', A, g['in'][0])      # claim they share a net, but no wire

        ok, log = self._emit_and_check('opened', opened)
        self.assertFalse(ok)
        self.assertIn('OPEN', log)

    def test_missing_port_is_detected(self):
        def missing(c):
            c.pin_in(0, 0, 'A')
            c.mark('ghost', (12345, 6789))  # not a real component port

        ok, log = self._emit_and_check('missing', missing)
        self.assertFalse(ok)
        self.assertIn('MISS', log)


if __name__ == '__main__':
    unittest.main()
