#!/usr/bin/env python3
#
#
# Copyright 2023 Kyle Dent <kdent@seaglass.com>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the “Software”), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
#

import pathlib
import re
import struct
import sys
from io import BytesIO

import PIL
from pdfminer.converter import PDFPageAggregator, PDFResourceManager
from pdfminer.layout import (
    LAParams,
    LTAnno,
    LTChar,
    LTCurve,
    LTFigure,
    LTImage,
    LTLine,
    LTRect,
    LTTextBoxHorizontal,
    LTTextLineHorizontal,
)
from pdfminer.pdfcolor import (
    LITERAL_DEVICE_CMYK,
    LITERAL_DEVICE_GRAY,
    LITERAL_DEVICE_RGB,
)
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdftypes import LITERALS_DCT_DECODE
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

fontmap = {
    "TimesNewRomanPSMT": "Times-Roman",
    "TimesNewRomanPS-ItalicMT": "Times-Italic",
    "TimesNewRomanPS-BoldItalicMT": "Times-BoldItalic",
    "TimesNewRomanPS-BoldMT": "Times-Bold",
    "ArialMT": "Helvetica",
    "Arial-ItalicMT": "Helvetica-Oblique",
    "Arial-BoldMT": "Helvetica-Bold",
    "Arial-BoldItalicMT": "Helvetica-BoldOblique",
    "CambriaMath": "Times-Roman",
    "Calibri": "Helvetica",
    "Corbel": "Helvetica",
    "CourierNew": "Courier",
    "CourierNewPSMT": "Courier",
    "Arial": "Helvetica",
    "Arial,Bold": "Helvetica-Bold",
    "Arial,BoldItalic": "Helvetica-BoldOblique",
    "QuickTypeII": "Helvetica",
    "QuickTypeII,Italic": "Helvetica-Oblique",
    "QuickTypeII,Bold": "Helvetica-Bold",
    "QuickTypeIICondensed": "Helvetica",
    "QuickTypeIICondensed,Bold": "Helvetica-Bold",
    "QuickTypeIICourierA": "Courier",
    "QuickTypeIIPi": "Helvetica",
    "UniversLTStd-Light": "Helvetica",
    "Univers_LT_Std_45_LightBold": "Helvetica-Bold",
    "Univers_LT_Std_47_Cn_LtBold": "Helvetica-Bold",
    "Univers_LT_Std_47_Cn_Lt": "Helvetica",
    "Univers_LT_Std_57_Cn": "Helvetica",
    "Univers_LT_Std_55": "Helvetica",
    "Univers_LT_67_CondensedBoldBold": "Helvetica-Bold",
    "Verdana": "Helvetica",
    "Wingdings-Regular": "ZapfDingbats",
    "Wingdings2": "ZapfDingbats",
}
DEFAULT_FONT = "Times-Roman"

if len(sys.argv) != 2:
    sys.stderr.write(f"usage: {sys.argv[0]} <pdf_file>\n")
    sys.exit(1)

pdf_file = sys.argv[1]


##########################################
# Function definitions
##########################################


def get_output_filename(input_filepath):
    file_path = pathlib.Path(input_filepath)
    return str(
        file_path.with_name(file_path.stem + "-unredacted" + file_path.suffix)
    )


def print_char(canvas, char_element):
    attrs = char_element.__dict__
    fontname = attrs["fontname"]
    fontname = re.sub("^[A-Z]{6}\+", "", fontname)
    if fontname in fontmap:
        fontname = fontmap[fontname]
    try:
        canvas.setFont(fontname, attrs["size"])
    except KeyError as err:
        print("unknown font:", err, "falling back to", DEFAULT_FONT)
        print("But you can add this font to the fontmap to improve the output.")
        canvas.setFont(DEFAULT_FONT, attrs["size"])

    set_canvas_colors(
        canvas,
        char_element.graphicstate.scolor,
        char_element.graphicstate.ncolor,
    )
    canvas.drawString(attrs["x0"], attrs["y0"], text=attrs["_text"])


def print_text_line(canvas, text_line_element):
    for element in text_line_element:
        if isinstance(element, LTChar):
            print_char(canvas, element)
        elif isinstance(element, LTAnno):
            None  # TODO: Not sure what to do with Annotations
        else:
            print("*******", type(element))
            print(element.__dict__)


#
#  BMPWriter
#
# This code is taken from the pdfminer.image source code to work with
# save_image() which is revised from pdfminer.image.export_image().
#
def align32(x):
    return ((x + 3) // 4) * 4


class BMPWriter:
    def __init__(self, fp, bits, width, height):
        self.fp = fp
        self.bits = bits
        self.width = width
        self.height = height
        if bits == 1:
            ncols = 2
        elif bits == 8:
            ncols = 256
        elif bits == 24:
            ncols = 0
        else:
            raise ValueError(bits)
        self.linesize = align32((self.width * self.bits + 7) // 8)
        self.datasize = self.linesize * self.height
        headersize = 14 + 40 + ncols * 4
        info = struct.pack(
            "<IiiHHIIIIII",
            40,
            self.width,
            self.height,
            1,
            self.bits,
            0,
            self.datasize,
            0,
            0,
            ncols,
            0,
        )
        assert len(info) == 40, len(info)
        header = struct.pack(
            "<ccIHHI", b"B", b"M", headersize + self.datasize, 0, 0, headersize
        )
        assert len(header) == 14, len(header)
        self.fp.write(header)
        self.fp.write(info)
        if ncols == 2:
            # B&W color table
            for i in (0, 255):
                self.fp.write(struct.pack("BBBx", i, i, i))
        elif ncols == 256:
            # grayscale color table
            for i in range(256):
                self.fp.write(struct.pack("BBBx", i, i, i))
        self.pos0 = self.fp.tell()
        self.pos1 = self.pos0 + self.datasize
        return

    def write_line(self, y, data):
        self.fp.seek(self.pos1 - (y + 1) * self.linesize)
        self.fp.write(data)
        return


def save_image(image, fp):
    """
    Format raw image data and save it to the file pointer in fp.
    This code is taken from the pdfminer.image source code and revised
    to work without actually writing the image data to a literal file.
    """
    stream = image.stream
    filters = stream.get_filters()
    (width, height) = image.srcsize
    if len(filters) == 1 and filters[0][0] in LITERALS_DCT_DECODE:
        ext = ".jpg"
    elif (
        image.bits == 1
        or image.bits == 8
        and image.colorspace in (LITERAL_DEVICE_RGB, LITERAL_DEVICE_GRAY)
    ):
        ext = ".%dx%d.bmp" % (width, height)
    else:
        ext = ".%d.%dx%d.img" % (image.bits, width, height)
    name = image.name + ext
    if ext == ".jpg":
        raw_data = stream.get_rawdata()
        if LITERAL_DEVICE_CMYK in image.colorspace:
            from PIL import Image, ImageChops

            ifp = BytesIO(raw_data)
            i = Image.open(ifp)
            i = ImageChops.invert(i)
            i = i.convert("RGB")
            i.save(fp, "JPEG")
        else:
            fp.write(raw_data)
    elif image.bits == 1:
        bmp = BMPWriter(fp, 1, width, height)
        data = stream.get_data()
        i = 0
        width = (width + 7) // 8
        for y in range(height):
            bmp.write_line(y, data[i : i + width])
            i += width
    elif image.bits == 8 and image.colorspace is LITERAL_DEVICE_RGB:
        bmp = BMPWriter(fp, 24, width, height)
        data = stream.get_data()
        i = 0
        width = width * 3
        for y in range(height):
            bmp.write_line(y, data[i : i + width])
            i += width
    elif image.bits == 8 and image.colorspace is LITERAL_DEVICE_GRAY:
        bmp = BMPWriter(fp, 8, width, height)
        data = stream.get_data()
        i = 0
        for y in range(height):
            bmp.write_line(y, data[i : i + width])
            i += width
    else:
        fp.write(stream.get_data())
        # Handle it like a bmp.
    #        if image.colorspace is LITERAL_DEVICE_GRAY:
    #            bmp = BMPWriter(fp, 8, width, height)
    #            data = stream.get_data()
    #            i = 0
    #            for y in range(height):
    #                bmp.write_line(y, data[i:i+width])
    #                i += width
    #        else:
    #            bmp = BMPWriter(fp, 24, width, height)
    #            data = stream.get_data()
    #            i = 0
    #            width = width*3
    #            for y in range(height):
    #                bmp.write_line(y, data[i:i+width])
    #                i += width

    fp.seek(0)
    return name


def set_canvas_colors(canvas, stroke_color, fill_color):
    # Set the stroke color
    if stroke_color != None:
        if isinstance(stroke_color, float) or stroke_color in [0, 1]:
            canvas.setStrokeGray(stroke_color)
        else:
            canvas.setStrokeColorRGB(*stroke_color)

    # Set the fill color
    if fill_color != None:
        if isinstance(fill_color, float) or fill_color in [0, 1]:
            canvas.setFillGray(fill_color)
        else:
            canvas.setFillColorRGB(*fill_color)


def print_image(canvas, element):
    attrs = element.__dict__
    width = attrs["width"]
    height = attrs["height"]
    img_fp = BytesIO()
    save_image(element, img_fp)
    try:
        img = PIL.Image.open(img_fp, mode="r")
        # Test whether image is all black or all white
        if sum(img.convert("L").getextrema()) in (0, 2):
            return  # Don't include it in revised PDF.
    except Exception as err:
        print(err)
        print(element)
        return

    c.drawImage(
        ImageReader(img), attrs["x0"], attrs["y0"], width=width, height=height
    )


if __name__ == "__main__":
    document = open(pdf_file, "rb")

    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)

    output_file = get_output_filename(pdf_file)
    c = canvas.Canvas(output_file, pageCompression=1)
    print("creating", output_file, end="", flush=True)

    page_count = 0
    for page in PDFPage.get_pages(document):
        page_count += 1
        text_lines = []
        print(".", end="", flush=True)
        interpreter.process_page(page)
        layout = device.get_result()
        c.setPageSize((layout.__dict__["width"], layout.__dict__["height"]))

        for element in layout:
            if isinstance(element, LTFigure):
                for subel in element:
                    if isinstance(subel, LTImage):
                        print_image(c, subel)
                    else:
                        # Print something out to indicate this has to be
                        # handled.
                        print("####")
                        print(type(subel), "        ", subel.__dict__)

            elif isinstance(element, LTImage):
                print_image(c, element)

            elif isinstance(element, LTChar):
                print_char(c, element)

            elif isinstance(element, LTTextBoxHorizontal):
                for subel in element:
                    if isinstance(subel, LTTextLineHorizontal):
                        #                        print_text_line(c, subel)
                        text_lines.append(subel)

            elif isinstance(element, LTTextLineHorizontal):
                print_text_line(c, element)

            elif isinstance(element, LTLine):
                attrs = element.__dict__
                c.setLineWidth(attrs["linewidth"] / 10)
                set_canvas_colors(
                    c, attrs["stroking_color"], attrs["non_stroking_color"]
                )
                c.line(attrs["x0"], attrs["y0"], attrs["x1"], attrs["y1"])

            elif isinstance(element, LTRect):
                attrs = element.__dict__

                # Skip redaction boxes
                if (
                    attrs["fill"] == True
                    and attrs["non_stroking_color"] in [None, 0]
                    and attrs["height"] > 2
                ):
                    continue

                # This is a hack and I don't know if it will mess up other
                # docs.  Lines used as underscores are too high up and cross
                # through the words they underline. I make an adjustment here
                # if it looks like a Rect is being used as an underline.
                #                y_adjust = 0
                #                if attrs['height'] < 1:
                y_adjust = -3

                c.setLineWidth(attrs["linewidth"] / 10)
                set_canvas_colors(
                    c, attrs["stroking_color"], attrs["non_stroking_color"]
                )

                c.rect(
                    attrs["x0"],
                    attrs["y0"] + y_adjust,
                    attrs["width"],
                    attrs["height"],
                    stroke=attrs["stroke"],
                    fill=attrs["fill"],
                )

            elif isinstance(element, LTCurve):
                attrs = element.__dict__
                c.setLineWidth(attrs["linewidth"] / 10)
                set_canvas_colors(
                    c, attrs["stroking_color"], attrs["non_stroking_color"]
                )
                p = c.beginPath()
                p.moveTo(attrs["x0"], attrs["y0"])
                for x, y in attrs["pts"]:
                    p.lineTo(x, y)

                c.drawPath(p, fill=attrs["fill"], stroke=attrs["stroke"])

            else:
                # Print out attribute information to indicate that this has
                # to be handled.
                print(type(element), element.__dict__)

        # Print text lines last so they aren't obscured by boxes, etc.
        for text_line in text_lines:
            print_text_line(c, text_line)

        c.showPage()

    print("saving", end="", flush=True)
    c.save()
    print()
