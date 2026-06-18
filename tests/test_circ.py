"""Tests for the .circ DSL (logikit.circ): gate geometry, wiring helpers, emit."""
import json
import os
import tempfile
import unittest

from logikit.circ import Circ, GATE_IN_DX, emit


class GateGeometryTest(unittest.TestCase):
    def test_output_and_two_inputs(self):
        c = Circ()
        g = c.gate(100, 200, 'AND')
        self.assertEqual(g['out'], (100, 200))
        # AND: DX = 50, inputs at (x-50, y-+20)
        self.assertEqual(g['in'], [(50, 180), (50, 220)])

    def test_three_input_adds_centre(self):
        c = Circ()
        g = c.gate(100, 200, 'NAND', n=3)          # NAND DX = 60
        self.assertEqual(g['in'], [(40, 180), (40, 200), (40, 220)])

    def test_dx_per_kind(self):
        # The whole point of the verified-geometry table: each gate kind has its
        # own input X-offset (body 50 + bubble/arc decorations).
        self.assertEqual(GATE_IN_DX,
                         {'AND': 50, 'OR': 50, 'NAND': 60, 'NOR': 60,
                          'XOR': 60, 'XNOR': 70})
        for kind, dx in GATE_IN_DX.items():
            g = Circ().gate(300, 100, kind)
            self.assertEqual(g['in'][0], (300 - dx, 80), kind)

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            Circ().gate(0, 0, 'BUFFER')

    def test_notg_is_width_30(self):
        g = Circ().notg(100, 50)
        self.assertEqual(g['out'], (100, 50))
        self.assertEqual(g['in'], [(70, 50)])

    def test_nand_inv_marks_real_pins(self):
        c = Circ()
        g = c.nand_inv(200, 100)
        self.assertEqual(g['out'], (200, 100))
        # the two physical NAND inputs (mark these, not the tie node)
        self.assertEqual(g['pins'], [(140, 80), (140, 120)])
        self.assertEqual(g['in'], [(130, 100)])    # tie node at x-70


class WiringHelperTest(unittest.TestCase):
    def test_w_rejects_non_orthogonal(self):
        with self.assertRaises(AssertionError):
            Circ().w((0, 0), (10, 10))

    def test_w_skips_zero_length(self):
        c = Circ()
        c.w((5, 5), (5, 5))
        self.assertEqual(c.parts, [])

    def test_fan_routes_trunk_and_marks_net(self):
        c = Circ()
        c.fan((0, 0), 100, [(200, 0), (200, 40)], net='n')
        # driver->trunk, vertical trunk, and one branch per receiver
        self.assertEqual(len(c.parts), 4)
        self.assertEqual(c.netof[(0, 0)], 'n')
        self.assertEqual(c.netof[(200, 0)], 'n')
        self.assertEqual(c.netof[(200, 40)], 'n')


class EmitTest(unittest.TestCase):
    def test_emit_writes_three_files(self):
        def half(c):
            A = c.pin_in(90, 100, 'A')
            B = c.pin_in(90, 260, 'B')
            g = c.nand(360, 180)
            Yo = c.pin_out(520, 180, 'Y')
            c.fan(A, 200, [g['in'][0]], net='A')
            c.fan(B, 180, [g['in'][1]], net='B')
            c.path(g['out'], Yo)
            c.mark('Y', g['out'])

        with tempfile.TemporaryDirectory() as d:
            circ, spec, fig = emit('half', half, d)
            for p in (circ, spec, fig):
                self.assertTrue(os.path.isfile(p))
            self.assertTrue(circ.endswith('half.circ'))
            self.assertTrue(fig.endswith('half_fig.circ'))

            circ_txt = open(circ).read()
            fig_txt = open(fig).read()
            self.assertIn('name="Pin"', circ_txt)        # real pins in .circ
            self.assertNotIn('name="Pin"', fig_txt)       # labels-only in _fig
            self.assertIn('name="Text"', fig_txt)

            mapping = json.load(open(spec))
            self.assertEqual(mapping['90,100'], 'A')      # "x,y" -> net
            self.assertEqual(mapping['520,180'], 'Y')


if __name__ == '__main__':
    unittest.main()
