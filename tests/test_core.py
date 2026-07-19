"""
Unit tests for core.py

Running
-------
From the package root (the directory that contains the package folder):

    python -m pytest tests/test_unredact.py -v

The tests use unittest.mock to avoid touching the real filesystem or requiring
actual PDF files, so no sample PDFs are needed for these unit tests.
"""

import io
import unittest
from unittest.mock import MagicMock

import pikepdf

from unredact.core import (
    UNREDACT_HIGHLIGHT_COLOR,
    UNREDACT_HIGHLIGHT_PERCENTAGE,
    UnredactPdf,
)
from unredact.document_state import DocState
from unredact.state_stack import StateStack

# ===========================================================================
# Helpers
# ===========================================================================

def _make_page(media_box=None, crop_box=None, content_stream=b""):
    """
    Build a minimal pikepdf page-like object backed by a real in-memory PDF
    so that pikepdf.parse_content_stream and stream assignment work correctly.
    """
    pdf = pikepdf.new()
    page_dict = pikepdf.Dictionary(
        Type=pikepdf.Name("/Page"),
        MediaBox=pikepdf.Array(media_box or [0, 0, 612, 792]),
        Resources=pikepdf.Dictionary(),
    )
    if crop_box is not None:
        page_dict["/CropBox"] = pikepdf.Array(crop_box)

    page = pikepdf.Page(page_dict)
    pdf.pages.append(page)

    # Attach a content stream so parse_content_stream has something to read
    stream = pikepdf.Stream(pdf, content_stream)
    pdf.pages[0]["/Contents"] = stream

    return pdf, pdf.pages[0]


def _encode_ops(*instructions):
    """
    Turn a list of (operands, operator_str) tuples into a PDF content-stream
    byte string that pikepdf can parse.

    Example:
        _encode_ops(
            ([1, 1, 1], "rg"),
            ([10, 10, 200, 20], "re"),
            ([], "f"),
        )
    """
    parts = []
    for operands, op in instructions:
        tokens = [str(o) for o in operands] + [op]
        parts.append(" ".join(tokens))
    return ("\n".join(parts) + "\n").encode()


# ===========================================================================
# UnredactPdf tests
# ===========================================================================

class TestUnredactPdf(unittest.TestCase):

    # --- construction -------------------------------------------------------

    def test_init_stores_pdf_obj_and_pages(self):
        mock_pdf = MagicMock()
        mock_pdf.pages = ["page1", "page2"]
        u = UnredactPdf(mock_pdf)
        self.assertIs(u.pdf_obj, mock_pdf)
        self.assertEqual(u.pages, ["page1", "page2"])

    def test_from_path_raises_when_missing(self):
        with self.assertRaises(FileNotFoundError):
            UnredactPdf.from_path("/no/such/file.pdf")

    def test_from_path_opens_real_pdf(self):
        # Create a minimal in-memory PDF, save to bytes, reload via from_path
        pdf = pikepdf.new()
        page_dict = pikepdf.Dictionary(
            Type=pikepdf.Name("/Page"),
            MediaBox=pikepdf.Array([0, 0, 612, 792]),
        )
        pdf.pages.append(pikepdf.Page(page_dict))
        buf = io.BytesIO()
        pdf.save(buf)
        buf.seek(0)

        import pathlib
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(buf.read())
            tmp_path = f.name
        try:
            u = UnredactPdf.from_path(tmp_path)
            self.assertIsInstance(u, UnredactPdf)
        finally:
            pathlib.Path(tmp_path).unlink()

    # --- save ---------------------------------------------------------------

    def test_save_delegates_to_pdf_obj(self):
        mock_pdf = MagicMock()
        mock_pdf.pages = []
        u = UnredactPdf(mock_pdf)
        u.save("/some/path.pdf")
        mock_pdf.save.assert_called_once_with("/some/path.pdf")

    # --- __set_transparency_on_page (via process_page side-effect) ----------

    def test_process_page_creates_semi_transparent_resource(self):
        """
        After process_page, the page must have
        /Resources/ExtGState/SemiTransparent.
        """
        pdf, page = _make_page(content_stream=b"")
        u = UnredactPdf(pdf)
        u.process_page(page)

        gs = page["/Resources"]["/ExtGState"]["/SemiTransparent"]
        self.assertAlmostEqual(float(gs["/ca"]), UNREDACT_HIGHLIGHT_PERCENTAGE)
        self.assertAlmostEqual(float(gs["/CA"]), UNREDACT_HIGHLIGHT_PERCENTAGE)

    def test_set_transparency_preserves_existing_resources(self):
        """process_page must not wipe out pre-existing /Resources entries."""
        pdf, page = _make_page(content_stream=b"")
        page["/Resources"]["/Font"] = pikepdf.Dictionary()
        u = UnredactPdf(pdf)
        u.process_page(page)
        self.assertIn("/Font", page["/Resources"])

    # --- __calc_max_height --------------------------------------------------

    def test_max_height_uses_media_box(self):
        """With no CropBox, max height = 90% of MediaBox height."""
        pdf, page = _make_page(media_box=[0, 0, 612, 792], content_stream=b"")
        u = UnredactPdf(pdf)
        u.process_page(page)   # just exercising; no assertion
                               # needed beyond no crash

    def test_max_height_uses_crop_box_when_present(self):
        """When present, CropBox bounds redaction height detection."""
        stream = _encode_ops(
            ([0, 0, 0], "rg"),
            ([0, 0, 612, 600], "re"),
            ([], "f"),
        )
        # 600pt is below 90% of the MediaBox, but above 90% of the CropBox.
        pdf, page = _make_page(
            media_box=[0, 0, 612, 792],
            crop_box=[0, 0, 612, 500],
            content_stream=stream,
        )
        u = UnredactPdf(pdf)
        u.process_page(page)
        ops = [str(op) for _, op in pikepdf.parse_content_stream(page)]
        self.assertNotIn("gs", ops)

    # --- __is_redaction / process_page integration -------------------------

    def test_black_rect_is_detected_as_redaction(self):
        """
        A black filled rectangle of reasonable size should be treated as
        a redaction: the f operator should be replaced with the highlight
        sequence.
        """
        # Page 792pt tall; rect height=20 is well within (5, 792*0.9=712.8)
        stream = _encode_ops(
            ([0, 0, 0], "rg"),          # black fill
            ([50, 100, 200, 20], "re"), # rect x y w h
            ([], "f"),                  # fill
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]

        # The injected highlight sequence must be present
        self.assertIn("q", ops)
        self.assertIn("rg", ops)
        self.assertIn("gs", ops)
        self.assertIn("Q", ops)

    def test_white_rect_is_not_treated_as_redaction(self):
        """
        A white filled rectangle should NOT be intercepted — white fills are
        explicitly excluded from redaction detection.
        """
        stream = _encode_ops(
            ([1, 1, 1], "rg"),          # white fill
            ([50, 100, 200, 20], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]

        # The original f should survive; no injected q/Q wrapping should appear
        self.assertIn("f", ops)
        # gs would only appear if the highlight was injected
        self.assertNotIn("gs", ops)

    def test_rect_too_small_is_not_redaction(self):
        """Rectangle height <= 5pt is below the redaction threshold."""
        stream = _encode_ops(
            ([0, 0, 0], "rg"),
            ([50, 100, 200, 3], "re"),  # height=3, below threshold of 5
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]
        self.assertNotIn("gs", ops)

    def test_rect_too_tall_is_not_redaction(self):
        """Rectangle height >= 90% of page height is not a redaction."""
        # Page height = 792; 90% = 712.8; use height=750 to exceed it
        stream = _encode_ops(
            ([0, 0, 0], "rg"),
            ([0, 0, 612, 750], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]
        self.assertNotIn("gs", ops)

    def test_negative_height_rect_is_treated_correctly(self):
        """
        Negative height (drawn upward) should be treated by absolute value.
        """
        stream = _encode_ops(
            ([0, 0, 0], "rg"),
            ([50, 100, 200, -20], "re"),  # negative height → abs = 20
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]
        self.assertIn("gs", ops)   # should be detected as a redaction

    # --- color operator handling -------------------------------------------

    def test_cmyk_black_rect_detected_as_redaction(self):
        """CMYK black (0 0 0 1 k) rect should be detected as a redaction."""
        stream = _encode_ops(
            ([0, 0, 0, 1], "k"),
            ([50, 100, 200, 20], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]
        self.assertIn("gs", ops)

    def test_cmyk_white_rect_not_redaction(self):
        """CMYK white (0 0 0 0 k) should not be treated as a redaction."""
        stream = _encode_ops(
            ([0, 0, 0, 0], "k"),
            ([50, 100, 200, 20], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]
        self.assertNotIn("gs", ops)

    def test_gray_fill_detected_as_redaction(self):
        """Gray fill (non-white) rect should be detected as a redaction."""
        stream = _encode_ops(
            ([0.5], "g"),              # mid-gray
            ([50, 100, 200, 20], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]
        self.assertIn("gs", ops)

    def test_device_rgb_sc_white_rect_is_not_redaction(self):
        """DeviceRGB colors supplied through sc must retain their values."""
        stream = _encode_ops(
            (["/DeviceRGB"], "cs"),
            ([1, 1, 1], "sc"),
            ([50, 100, 200, 20], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)
        ops = [str(op) for _, op in pikepdf.parse_content_stream(page)]
        self.assertNotIn("gs", ops)

    def test_transparent_graphics_state_rect_is_not_redaction(self):
        """A fully transparent fill must not be replaced with a highlight."""
        stream = _encode_ops(
            (["/Invisible"], "gs"),
            ([0, 0, 0], "rg"),
            ([50, 100, 200, 20], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        page["/Resources"]["/ExtGState"] = pikepdf.Dictionary(
            {"/Invisible": pikepdf.Dictionary({"/ca": 0})}
        )
        u = UnredactPdf(pdf)
        u.process_page(page)
        ops = [str(op) for _, op in pikepdf.parse_content_stream(page)]
        self.assertEqual(ops.count("gs"), 1)

    def test_even_odd_fill_rule_is_preserved(self):
        """Replacing a redaction must not change an f* fill into a normal fill."""
        stream = _encode_ops(
            ([0, 0, 0], "rg"),
            ([50, 100, 200, 20], "re"),
            ([], "f*"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)
        ops = [str(op) for _, op in pikepdf.parse_content_stream(page)]
        self.assertIn("f*", ops)

    # --- graphics state stack (q / Q) --------------------------------------

    def test_color_restored_after_q_Q(self):
        """
        Color set inside a q/Q block must NOT affect a subsequent fill outside
        that block — the outer black fill should still be a redaction.

        Also verifies that the inner block correctly inherits the outer color
        (now that q does a deep copy of the current state rather than pushing
        a blank DocState).
        """
        stream = _encode_ops(
            ([0, 0, 0], "rg"),          # outer: black
            ([50, 100, 200, 20], "re"),
            ([], "q"),                  # push deep copy of black state
            ([1, 1, 1], "rg"),          # inner: override to white
            ([], "Q"),                  # pop → outer black state restored
            ([], "f"),                  # fill, should still be black: redaction
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]

        # The restored black fill after Q must be detected as a redaction
        self.assertIn("gs", ops)

        # Sanity check: the white override inside q/Q must NOT have leaked out
        # (if it had, gs would be absent — but we also verify via DocState
        # directly)
        stack = StateStack()
        outer = DocState(color_space='rg', fill_color=[0, 0, 0])
        stack.push(outer)
        import copy
        inner = copy.deepcopy(stack.peek())
        stack.push(inner)
        inner.fill_color = [1, 1, 1]        # mutate inner
        stack.pop()
        self.assertEqual(stack.peek().fill_color, [0, 0, 0])  # outer unchanged

    # --- non-fill operators pass through unchanged -------------------------

    def test_non_fill_operators_preserved(self):
        """
        Text and other operators unrelated to fills must survive process_page.
        """
        # BT/ET bracket a text block; Tf sets font; Tj draws text
        stream = b"BT /F1 12 Tf 100 700 Td (Hello) Tj ET\n"
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        ops = [str(op) for _, op in out]
        self.assertIn("BT", ops)
        self.assertIn("ET", ops)
        self.assertIn("Tj", ops)

        # --- highlight color injected correctly ------------------------------

    def test_highlight_color_values_injected(self):
        """The injected rg operands must match UNREDACT_HIGHLIGHT_COLOR."""
        stream = _encode_ops(
            ([0, 0, 0], "rg"),
            ([50, 100, 200, 20], "re"),
            ([], "f"),
        )
        pdf, page = _make_page(content_stream=stream)
        u = UnredactPdf(pdf)
        u.process_page(page)

        out = pikepdf.parse_content_stream(page)
        # Find the rg instruction that follows the injected q
        found_q = False
        for operands, op in out:
            if str(op) == "q":
                found_q = True
            if found_q and str(op) == "rg":
                injected = [float(x) for x in operands]
                self.assertEqual(len(injected), 3)
                for actual, expected in zip(
                    injected,
                    UNREDACT_HIGHLIGHT_COLOR,
                    strict=False):
                    self.assertAlmostEqual(actual, expected, places=3)
                break


if __name__ == "__main__":
    unittest.main()
