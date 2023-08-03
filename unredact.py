"""Top level driver script for unredacting PDF files."""

import sys

from unredact.__main__ import get_output_filename, main

if len(sys.argv) != 2:
    sys.stderr.write(f"usage: {sys.argv[0]} <pdf_file>\n")
    sys.exit(1)

pdf_file = sys.argv[1]
output_pdf = get_output_filename(pdf_file)

main(pdf_file, output_pdf)
