#!/usr/bin/env python3

"""Top level driver script for unredacting PDF files."""

import sys
import unredact

if len(sys.argv) != 2:
    sys.stderr.write(f"usage: {sys.argv[0]} <pdf_file>\n")
    sys.exit(1)

pdf_file = sys.argv[1]
output_pdf = unredact.get_output_filename(pdf_file)

unredact.main(pdf_file, output_pdf)
