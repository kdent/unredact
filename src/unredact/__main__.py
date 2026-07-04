from unredact.core import UnredactPdf
import pathlib
import pikepdf
import sys

def main():

    if len(sys.argv) != 2:
        sys.stderr.write(f"usage: {sys.argv[0]} <pdf_file>\n")
        sys.exit(1)

    pdf_file = sys.argv[1]
    output_pdf = get_output_filename(pdf_file)

    pdf = UnredactPdf.from_path(pdf_file)

    for page in pdf.pages:
        pdf.process_page(page)

    pdf.save('pikepdf_unredacted.pdf')
#    pdf.save(output_pdf)
#    print(f"Saved changes to: {output_pdf}")


def get_output_filename(input_filepath):
    """Retrieve the output file name."""
    file_path = pathlib.Path(input_filepath)
    return str(
        file_path.with_name(file_path.stem + "-unredacted" + file_path.suffix)
    )



if __name__ == "__main__":
    main()
