import unittest

from unredact.document_state import DocState

# ===========================================================================
# DocState tests
# ===========================================================================

class TestDocState(unittest.TestCase):

    # --- construction -------------------------------------------------------

    def test_default_construction(self):
        s = DocState()
        self.assertEqual(s.rectangle_dimensions, [0, 0, 0, 0])
        self.assertEqual(s.color_space, 'rg')
        self.assertEqual(s.fill_color, [0, 0, 0])
        self.assertFalse(s.fill_transparent)

    def test_custom_construction(self):
        s = DocState(rectangle_dimensions=[1, 2, 3, 4], color_space='k',
                     fill_color=[0, 0, 0, 0])
        self.assertEqual(s.rectangle_dimensions, [1, 2, 3, 4])
        self.assertEqual(s.color_space, 'k')
        self.assertEqual(s.fill_color, [0, 0, 0, 0])

    # --- is_fill_color_white : RGB ------------------------------------------

    def test_rgb_white(self):
        s = DocState(color_space='rg', fill_color=[1, 1, 1])
        self.assertTrue(s.is_fill_color_white())

    def test_rgb_black_not_white(self):
        s = DocState(color_space='rg', fill_color=[0, 0, 0])
        self.assertFalse(s.is_fill_color_white())

    def test_rgb_partial_not_white(self):
        s = DocState(color_space='rg', fill_color=[1, 0, 1])
        self.assertFalse(s.is_fill_color_white())

    # --- is_fill_color_white : CMYK -----------------------------------------

    def test_cmyk_white(self):
        # CMYK white = zero ink on all channels
        s = DocState(color_space='k', fill_color=[0, 0, 0, 0])
        self.assertTrue(s.is_fill_color_white())

    def test_cmyk_black_not_white(self):
        s = DocState(color_space='k', fill_color=[0, 0, 0, 1])
        self.assertFalse(s.is_fill_color_white())

    def test_cmyk_colored_not_white(self):
        s = DocState(color_space='k', fill_color=[0.5, 0, 0, 0])
        self.assertFalse(s.is_fill_color_white())

    # --- is_fill_color_white : Grayscale ------------------------------------

    def test_gray_white(self):
        # NOTE: DocState treats 0 as black
        s = DocState(color_space='g', fill_color=[0])
        self.assertFalse(s.is_fill_color_white())

    def test_gray_black_not_white(self):
        s = DocState(color_space='g', fill_color=[1])
        self.assertTrue(s.is_fill_color_white())

    def test_set_gray_fill_color_white(self):
        s = DocState(color_space='g', fill_color=[0])
        s.set_fill_color_white()
        self.assertTrue(s.is_fill_color_white())

    # --- is_fill_color_white : invalid color space --------------------------

    def test_invalid_color_space_raises(self):
        s = DocState(color_space='xyz', fill_color=[0])
        with self.assertRaises(ValueError):
            s.is_fill_color_white()
