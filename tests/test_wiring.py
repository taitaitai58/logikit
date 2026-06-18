"""Tests for breadboard/DIP wiring-diagram geometry (logikit.wiring).

These exercise the pure-Python layout/TikZ generation only; actually compiling a
PDF needs ``lualatex`` and is covered by a single skipped-if-absent smoke test.
"""
import shutil
import tempfile
import unittest

from logikit.wiring import Scene, pin_col, render_scene


class PinColTest(unittest.TestCase):
    def test_top_and_bottom_rows(self):
        # top row left->right: 7 6 5 4 3 2 1 ; bottom: 14 13 12 11 10 9 8
        self.assertEqual(pin_col(7), 0)
        self.assertEqual(pin_col(1), 6)
        self.assertEqual(pin_col(14), 0)
        self.assertEqual(pin_col(8), 6)

    def test_pin_region(self):
        s = Scene(1)
        self.assertEqual(s._region(('P', 0, 3)), 'top')     # pins 1-7 are top
        self.assertEqual(s._region(('P', 0, 10)), 'bot')    # pins 8-14 are bottom
        self.assertEqual(s._region(('E', 2)), 'top')        # electrodes are top


class StarRoutingTest(unittest.TestCase):
    def test_k_terminal_net_makes_k_minus_1_cables(self):
        s = Scene(1)
        s.net([('E', 1), ('P', 0, 4)])                       # 1 cable
        s.net([('E', 3), ('P', 0, 1), ('P', 0, 2), ('P', 0, 10)])  # 3 cables
        s.layout()
        self.assertEqual(len(s.cables), 1 + 3)
        # every cable joins exactly two terminals (no branching)
        for cab in s.cables:
            self.assertIn('a', cab)
            self.assertIn('b', cab)

    def test_power_nets_fan_one_cable_per_ic(self):
        s = Scene(2)
        s.gnd_net()
        s.vcc_net()
        s.layout()
        self.assertEqual(len(s.cables), 2 + 2)               # 2 ICs each for GND/Vcc

    def test_full_mux2_scene_cable_count(self):
        # Mirrors examples/breadboard.py: 8 signal cables + GND + Vcc = 10.
        s = Scene(1)
        s.net([('E', 1), ('P', 0, 4)])
        s.net([('E', 2), ('P', 0, 9)], side='L')
        s.net([('E', 3), ('P', 0, 1), ('P', 0, 2), ('P', 0, 10)])
        s.net([('P', 0, 3), ('P', 0, 5)])
        s.net([('P', 0, 6), ('P', 0, 12)])
        s.net([('P', 0, 8), ('P', 0, 13)])
        s.gnd_net()
        s.vcc_net()
        s.layout()
        self.assertEqual(len(s.cables), 10)


class TikzTest(unittest.TestCase):
    def test_tikz_contains_boxes_and_labels(self):
        s = Scene(1)
        s.ic_tags = {0: 'IC1'}
        s.net([('E', 1), ('P', 0, 4)])
        s.layout()
        tikz = s.tikz()
        self.assertIn('論理箱', tikz)        # default Japanese logic-box label
        self.assertIn('電源箱', tikz)        # default power-box label
        self.assertIn('IC1', tikz)
        self.assertIn(r'\draw', tikz)

    def test_latin_labels(self):
        s = Scene(1)
        s.logic_label, s.power_label = 'Logic box', 'Power box'
        s.net([('E', 1), ('P', 0, 4)])
        s.layout()
        tikz = s.tikz()
        self.assertIn('Logic box', tikz)
        self.assertNotIn('論理箱', tikz)


@unittest.skipUnless(shutil.which('lualatex'), 'lualatex not installed')
class RenderSmokeTest(unittest.TestCase):
    def test_render_produces_pdf(self):
        from logikit.wiring import DOC_LATIN
        s = Scene(1)
        s.logic_label, s.power_label = 'Logic box', 'Power box'
        s.net([('E', 1), ('P', 0, 4)])
        s.gnd_net()
        s.vcc_net()
        with tempfile.TemporaryDirectory() as d:
            pdf = render_scene(s, 'smoke', d, doc=DOC_LATIN)
            self.assertTrue(pdf.endswith('.pdf'))


if __name__ == '__main__':
    unittest.main()
