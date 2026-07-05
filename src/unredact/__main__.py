import argparse
import pathlib
import sys

from unredact.core import UnredactPdf

VERSION = "1.0"


def main():

    #
    # Set up command line arguments.
    #
    parser = argparse.ArgumentParser(
        prog="unredact", description="Remove weak redactions from PDF files"
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {VERSION}",
        help="show the program version and exit",
    )
    parser.add_argument(
        "-o",
        "--output_dir",
        type=str,
        default=".",
        required=False,
        help=(
            "specify an output directory where unredacted"
            "PDF files will be written"
        ),
    )
    parser.add_argument(
        "pdf_files", nargs="+", help="list of PDF files to process"
    )
    args = parser.parse_args()

    # Make sure specified directory is available for writing.
    output_path = pathlib.Path(args.output_dir)
    temp_file = output_path / ".write_test"
    try:
        temp_file.write_bytes(b"")  # Try to create a file in the output
        # directory
        temp_file.unlink()  # Clean up the test file
    except PermissionError:
        print(f"Unable to write to {output_path}.", file=sys.stderr)
        sys.exit(-2)

    # Process the PDF files given on the command line.
    for pdf_file in args.pdf_files:
        # Open the file through the UnredactPdf library.
        output_pdf = get_output_file_path(pdf_file, args.output_dir)
        try:
            pdf = UnredactPdf.from_path(pdf_file)
            print("processing", pdf_file)
        except Exception as error:
            print(f"Cannot access {pdf_file}:", error, file=sys.stderr)
            continue

        # Process each page in the file.
        for page in pdf.pages:
            pdf.process_page(page)

        pdf.save("pikepdf_unredacted.pdf")
        #        pdf.save(output_pdf)
        print(f"saved changes to: {output_pdf}")


def get_output_file_path(input_filepath, output_dir):
    """Retrieve the output file name."""
    file_path = pathlib.Path(input_filepath)
    out_path = pathlib.Path(output_dir)
    output_filename = file_path.stem + "-unredacted" + file_path.suffix
    return out_path / output_filename


if __name__ == "__main__":
    main()
